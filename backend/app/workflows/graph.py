"""The employee-request LangGraph workflow (Phase 5).

    classify -> retrieve_policy -> [plan -> risk_check -> execute -> verify] -> respond

The bracketed steps only run for intents with a matching mock tool
(`app.agents.nodes.TOOL_INTENTS`); everything else answers from the
retrieved policy alone. `risk_check` can also short-circuit straight to
`respond` (skipping `execute`/`verify` entirely) when it escalates a
request for human review, and `execute` skips `verify` whenever the tool
call itself didn't come back APPROVED - see `app.agents.nodes` for exactly
what each node does and why.
"""

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agents.nodes import (
    WorkflowNodes,
    route_after_execute,
    route_after_retrieve,
    route_after_risk_check,
)
from app.agents.state import WorkflowState
from app.models.request import Request


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
    return graph.invoke(initial_state)
