"""The employee-request LangGraph workflow (Phase 5).

    classify -> retrieve_policy -> [plan -> risk_check -> execute -> verify] -> respond

The bracketed steps only run for intents with a matching mock tool
(`app.agents.nodes.TOOL_INTENTS`); everything else answers from the
retrieved policy alone. `risk_check` can also short-circuit straight to
`respond` (skipping `execute`/`verify` entirely) when it escalates a
request for human review, and `execute` skips `verify` whenever the tool
call itself didn't come back APPROVED - see `app.agents.nodes` for exactly
what each node does and why.

Both graphs run via `.stream(..., stream_mode="updates")` rather than
`.invoke()` (Phase 7): streaming yields one `{node_name: partial_state}`
update per node as it completes, which `_run_graph_with_events` both folds
into a running state dict (equivalent to what `.invoke()` would have
returned, since every field here is last-write-wins) and logs as a
`WorkflowEvent` - so the audit timeline comes from the graph's own
execution trace instead of instrumenting every node individually.
"""

from typing import Any

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agents.nodes import (
    WorkflowNodes,
    route_after_decision,
    route_after_execute,
    route_after_retrieve,
    route_after_risk_check,
)
from app.agents.state import WorkflowState
from app.models.request import Request
from app.services.audit import record_workflow_event


def build_workflow_graph(db: Session):
    nodes = WorkflowNodes(db)
    graph = StateGraph(WorkflowState)

    graph.add_node("classify", nodes.classify)
    graph.add_node("retrieve_policy", nodes.retrieve_policy)
    graph.add_node("plan", nodes.plan)
    graph.add_node("risk_check", nodes.risk_check)
    graph.add_node("execute", nodes.execute)
    graph.add_node("verify", nodes.verify)
    graph.add_node("respond", nodes.respond)

    graph.add_edge(START, "classify")
    graph.add_edge("classify", "retrieve_policy")
    graph.add_conditional_edges(
        "retrieve_policy", route_after_retrieve, {"plan": "plan", "respond": "respond"}
    )
    graph.add_edge("plan", "risk_check")
    graph.add_conditional_edges(
        "risk_check", route_after_risk_check, {"execute": "execute", "respond": "respond"}
    )
    graph.add_conditional_edges(
        "execute", route_after_execute, {"verify": "verify", "respond": "respond"}
    )
    graph.add_edge("verify", "respond")
    graph.add_edge("respond", END)

    return graph.compile()


def _run_graph_with_events(graph: Any, initial_state: WorkflowState, db: Session) -> WorkflowState:
    request_id = initial_state["request_id"]
    state: dict[str, Any] = dict(initial_state)
    try:
        for update in graph.stream(initial_state, stream_mode="updates"):
            for node_name, partial in update.items():
                state.update(partial)
                record_workflow_event(db, request_id, node_name, partial)
    except Exception as exc:
        # A node raised (e.g. `execute` refusing to run an incomplete plan -
        # see app.agents.nodes.WorkflowNodes.execute). Log the failure to the
        # timeline before re-raising so it isn't silently missing from the
        # audit trail just because this run didn't reach `respond`.
        record_workflow_event(db, request_id, "workflow_error", {"error": str(exc)})
        raise
    return state  # type: ignore[return-value]


def apply_run_result(request: Request, final_state: WorkflowState) -> None:
    """Write a graph run's final state back onto its `Request` row.

    Shared by `app.api.requests`, `app.web.routes`, and
    `app.evaluation.runner` so "what a run produced" and "how that gets
    persisted" stay defined in exactly one place. Does not commit - the
    caller controls the transaction (e.g. so it can also write an
    `approval_decision` event and commit both together).
    """
    request.intent = final_state.get("intent")
    request.classification_confidence = final_state.get("confidence")
    request.classification_reasoning = final_state.get("reasoning")
    # Not `X or None`: the graph's initial state always seeds these as
    # `[]`/`{}` (see below), so a node that legitimately ran and found
    # nothing (e.g. a plan with zero extractable arguments) is a real `{}`,
    # not "this step never ran".
    request.retrieved_policy = final_state.get("retrieved_chunks")
    request.plan_tool_name = final_state.get("plan_tool_name")
    request.plan_arguments = final_state.get("plan_arguments")
    request.risk_level = final_state.get("risk_level")
    request.risk_flags = final_state.get("risk_flags")
    if final_state.get("tool_execution_id"):
        request.tool_execution_id = final_state["tool_execution_id"]
    request.status = final_state["status"]
    request.final_response = final_state.get("final_response")


def run_request_workflow(db: Session, request: Request) -> WorkflowState:
    """Run the full workflow for a request and return its final state.

    Does not write the result back onto `request` itself - the caller (see
    `app.api.requests.run_request_workflow_endpoint`) does that in one
    commit once the graph has finished, so a request's row only ever
    reflects a fully-run (not partially-run) pass through the workflow.
    """
    graph = build_workflow_graph(db)
    initial_state: WorkflowState = {
        "request_id": request.id,
        "employee_id": request.employee_id,
        "raw_query": request.raw_query,
        "retrieved_chunks": [],
        "plan_arguments": {},
        "risk_flags": [],
        "escalate": False,
        "status": request.status,
    }
    return _run_graph_with_events(graph, initial_state, db)


def build_resume_graph(db: Session):
    """The resume half of the workflow (Phase 6): apply_decision -> [execute
    -> verify] -> respond. Reuses the same `execute`/`verify`/`respond` node
    implementations `build_workflow_graph` uses, so a tool call triggered by
    a human's approval is handled identically to one triggered automatically.
    """
    nodes = WorkflowNodes(db)
    graph = StateGraph(WorkflowState)

    graph.add_node("apply_decision", nodes.apply_decision)
    graph.add_node("execute", nodes.execute)
    graph.add_node("verify", nodes.verify)
    graph.add_node("respond", nodes.respond)

    graph.add_edge(START, "apply_decision")
    graph.add_conditional_edges(
        "apply_decision",
        route_after_decision,
        {"execute": "execute", "verify": "verify", "respond": "respond"},
    )
    graph.add_conditional_edges(
        "execute", route_after_execute, {"verify": "verify", "respond": "respond"}
    )
    graph.add_edge("verify", "respond")
    graph.add_edge("respond", END)

    return graph.compile()


def run_request_resume(db: Session, request: Request, decision: str) -> WorkflowState:
    """Resume a request sitting at AWAITING_APPROVAL with a human decision.

    Rehydrates the workflow state from what the first run already persisted
    onto `request` (there's no separate durable graph checkpoint - the
    `Request` row itself is the checkpoint) and runs the resume graph from
    `apply_decision`. See `build_resume_graph` for what happens next
    depending on whether a tool already ran.
    """
    graph = build_resume_graph(db)
    initial_state: WorkflowState = {
        "request_id": request.id,
        "employee_id": request.employee_id,
        "raw_query": request.raw_query,
        "intent": request.intent,
        "confidence": request.classification_confidence,
        "reasoning": request.classification_reasoning,
        "retrieved_chunks": request.retrieved_policy or [],
        "plan_tool_name": request.plan_tool_name,
        "plan_arguments": request.plan_arguments or {},
        "risk_level": request.risk_level,
        "risk_flags": request.risk_flags or [],
        "tool_execution_id": request.tool_execution_id,
        "approval_decision": decision,
        "status": request.status,
    }
    return _run_graph_with_events(graph, initial_state, db)
