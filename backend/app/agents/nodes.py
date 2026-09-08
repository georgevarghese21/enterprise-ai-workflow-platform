"""Node implementations for the employee-request LangGraph workflow (Phase 5+).

Each node is a bound method on `WorkflowNodes` so it can hold the DB session
it needs (LangGraph nodes are plain `state -> partial state` callables and
have no dependency-injection mechanism of their own). Nodes that touch tools
or resources go through the same functions/tables Phase 4 already built:
`app.tools.*` for the business rules and `persist_tool_execution` for
logging, so a request processed by the workflow is indistinguishable in
`tool_executions` from one triggered directly via `/api/tools/*`.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.state import WorkflowState
from app.models.employee import Employee
from app.models.enums import RequestIntent, RiskLevel, ToolExecutionStatus, WorkflowStatus
from app.models.resource import Resource
from app.models.tool_execution import ToolExecution
from app.rag.retrieve import search_policy_chunks
from app.services.llm_provider import get_llm_provider
from app.services.tool_execution import persist_tool_execution
from app.tools.data_access import grant_data_access
from app.tools.expense import submit_expense
from app.tools.it_ticket import ITTicketCategory, create_it_ticket
from app.tools.travel import book_travel

# Intents with a matching mock tool (app.services.llm_provider._INTENT_TOOL_NAME
# has the intent -> tool_name half of this mapping; TOOL_INTENTS is just its
# key set, used to route requests with no automatable tool straight to a
# policy-only response).
TOOL_INTENTS = frozenset(
    {
        RequestIntent.DATA_ACCESS,
        RequestIntent.IT_EQUIPMENT,
        RequestIntent.IT_SOFTWARE,
        RequestIntent.TRAVEL_BOOKING,
        RequestIntent.EXPENSE_REIMBURSEMENT,
    }
)

_RISK_ORDER = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH]


def _max_risk(a: RiskLevel, b: RiskLevel) -> RiskLevel:
    return a if _RISK_ORDER.index(a) >= _RISK_ORDER.index(b) else b


class WorkflowNodes:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.llm = get_llm_provider()

    def classify(self, state: WorkflowState) -> dict[str, Any]:
        result = self.llm.classify(state["raw_query"])
        return {
            "intent": result.intent,
            "confidence": result.confidence,
            "reasoning": result.reasoning,
            "status": WorkflowStatus.CLASSIFIED,
        }

    def retrieve_policy(self, state: WorkflowState) -> dict[str, Any]:
        retrieved = search_policy_chunks(self.db, state["raw_query"], top_k=3)
        chunks = [
            {
                "chunk_id": r.chunk.id,
                "document": r.chunk.document_name,
                "title": r.chunk.title,
                "content": r.chunk.content,
                "score": r.score,
            }
            for r in retrieved
        ]
        return {"retrieved_chunks": chunks, "status": WorkflowStatus.POLICY_RETRIEVED}

    def plan(self, state: WorkflowState) -> dict[str, Any]:
        intent = state["intent"]
        assert intent is not None, "plan is only reached once classify has set an intent"
        known_resource_names: list[str] = []
        if intent == RequestIntent.DATA_ACCESS:
            known_resource_names = list(self.db.scalars(select(Resource.name)))

        tool_plan = self.llm.plan(intent, state["raw_query"], known_resource_names)
        return {
            "plan_tool_name": tool_plan.tool_name,
            "plan_arguments": tool_plan.arguments,
            "plan_notes": tool_plan.notes,
            "status": WorkflowStatus.PLANNED,
        }

    def risk_check(self, state: WorkflowState) -> dict[str, Any]:
        flags: list[str] = []
        escalate = False
        risk_level = RiskLevel.LOW

        employee = self.db.get(Employee, state["employee_id"])
        if employee is None or not employee.active:
            flags.append("employee_inactive_or_not_found")
            escalate = True
            risk_level = RiskLevel.HIGH

        confidence = state.get("confidence")
        if confidence is not None and confidence < 0.5:
            flags.append("low_classification_confidence")
            escalate = True
            risk_level = _max_risk(risk_level, RiskLevel.MEDIUM)

        tool_name = state.get("plan_tool_name")
        arguments = state.get("plan_arguments") or {}

        if tool_name == "grant_data_access":
            resource = None
            resource_name = arguments.get("resource_name")
            if resource_name:
                resource = self.db.scalar(select(Resource).where(Resource.name == resource_name))
            if resource is None:
                flags.append("incomplete_tool_arguments")
                escalate = True
                risk_level = _max_risk(risk_level, RiskLevel.MEDIUM)
            elif resource.sensitivity.value == "HIGH":
                risk_level = _max_risk(risk_level, RiskLevel.MEDIUM)

        elif tool_name == "book_travel":
            if "destination" not in arguments or "total_cost_usd" not in arguments:
                flags.append("incomplete_tool_arguments")
                escalate = True
                risk_level = _max_risk(risk_level, RiskLevel.MEDIUM)
            elif arguments["total_cost_usd"] > 1000:
                risk_level = _max_risk(risk_level, RiskLevel.MEDIUM)

        elif tool_name == "submit_expense":
            if "amount_usd" not in arguments:
                flags.append("incomplete_tool_arguments")
                escalate = True
                risk_level = _max_risk(risk_level, RiskLevel.MEDIUM)
            elif arguments["amount_usd"] > 1000:
                risk_level = _max_risk(risk_level, RiskLevel.MEDIUM)

        elif tool_name == "create_it_ticket":
            if arguments.get("category") in ("EQUIPMENT_NON_STANDARD", "SOFTWARE_NEW"):
                risk_level = _max_risk(risk_level, RiskLevel.MEDIUM)

        return {
            "risk_level": risk_level,
            "risk_flags": flags,
            "escalate": escalate,
            "status": WorkflowStatus.AWAITING_APPROVAL if escalate else state["status"],
        }

    def execute(self, state: WorkflowState) -> dict[str, Any]:
        employee = self.db.get(Employee, state["employee_id"])
        if employee is None:
            raise ValueError(f"Employee {state['employee_id']} not found during execute")
        tool_name = state["plan_tool_name"]
        arguments = state.get("plan_arguments") or {}

        if tool_name == "grant_data_access":
            if "resource_name" not in arguments:
                raise ValueError(
                    "Cannot execute grant_data_access: no resource_name in the plan. "
                    "This request's plan was incomplete when it was escalated for "
                    "approval - approving it doesn't supply the missing resource name, "
                    "so it can't be auto-executed. Ask the employee to resubmit "
                    "naming the resource explicitly, or call /api/tools/data-access "
                    "directly with the correct resource."
                )
            resource = self.db.scalar(
                select(Resource).where(Resource.name == arguments["resource_name"])
            )
            if resource is None:
                raise ValueError(
                    f"Resource {arguments['resource_name']!r} not found during execute "
                    "(risk_check should have caught this - it re-runs the same lookup)"
                )
            result = grant_data_access(employee, resource, arguments.get("duration_days"))
            input_payload = {
                "resource_name": resource.name,
                "duration_days": arguments.get("duration_days"),
            }
        elif tool_name == "create_it_ticket":
            category = ITTicketCategory(arguments["category"])
            description = arguments.get("description", state["raw_query"])
            cost = arguments.get("equipment_cost_usd")
            result = create_it_ticket(employee, category, description, cost)
            input_payload = {
                "category": category.value,
                "description": description,
                "equipment_cost_usd": cost,
            }
        elif tool_name == "book_travel":
            if "destination" not in arguments or "total_cost_usd" not in arguments:
                raise ValueError(
                    "Cannot execute book_travel: destination and/or total_cost_usd is "
                    "missing from the plan. Approving an escalated request doesn't "
                    "supply missing details - ask the employee to resubmit with the "
                    "destination and cost stated explicitly."
                )
            result = book_travel(
                employee,
                arguments["destination"],
                arguments.get("is_international", False),
                arguments["total_cost_usd"],
            )
            input_payload = {
                "destination": arguments["destination"],
                "is_international": arguments.get("is_international", False),
                "total_cost_usd": arguments["total_cost_usd"],
            }
        elif tool_name == "submit_expense":
            if "amount_usd" not in arguments:
                raise ValueError(
                    "Cannot execute submit_expense: amount_usd is missing from the "
                    "plan. Approving an escalated request doesn't supply missing "
                    "details - ask the employee to resubmit with a dollar amount "
                    "stated explicitly."
                )
            description = arguments.get("description", state["raw_query"])
            result = submit_expense(employee, arguments["amount_usd"], description)
            input_payload = {"amount_usd": arguments["amount_usd"], "description": description}
        else:
            raise ValueError(f"No executable tool for plan_tool_name={tool_name!r}")

        execution = persist_tool_execution(
            self.db, tool_name, employee.id, state["request_id"], input_payload, result
        )

        next_status = {
            ToolExecutionStatus.APPROVED: WorkflowStatus.VERIFYING,
            ToolExecutionStatus.PENDING_APPROVAL: WorkflowStatus.AWAITING_APPROVAL,
            ToolExecutionStatus.DENIED: WorkflowStatus.REJECTED,
        }[result.status]

        return {
            "tool_execution_id": execution.id,
            "tool_status": result.status,
            "status": next_status,
        }

    def verify(self, state: WorkflowState) -> dict[str, Any]:
        execution = self.db.get(ToolExecution, state["tool_execution_id"])
        verified = execution is not None and execution.status == ToolExecutionStatus.APPROVED
        return {"status": WorkflowStatus.COMPLETED if verified else WorkflowStatus.FAILED}

    def apply_decision(self, state: WorkflowState) -> dict[str, Any]:
        """Entry node of the resume graph (Phase 6+): applies a human's
        approve/reject decision to a request that's sitting at
        AWAITING_APPROVAL, and figures out where the workflow should
        continue from.

        Two cases, distinguished by whether `tool_execution_id` is set:
          - Not set: `risk_check` escalated *before* any tool ran (e.g. an
            inactive employee, a low-confidence classification, an
            incomplete plan). Approving means "go ahead and run the tool
            now"; rejecting just ends the request with no tool ever called.
          - Set: the tool itself already ran and returned PENDING_APPROVAL
            (its own approval tier, e.g. MEDIUM/HIGH sensitivity data
            access). Approving/rejecting overrides that tool_executions
            row's status directly rather than calling the tool again.
        """
        decision = state["approval_decision"]
        tool_execution_id = state.get("tool_execution_id")

        if decision == "REJECTED":
            if tool_execution_id:
                execution = self.db.get(ToolExecution, tool_execution_id)
                if execution is not None:
                    execution.status = ToolExecutionStatus.DENIED
                    self.db.commit()
            return {"status": WorkflowStatus.REJECTED, "resolved_by_human": True}

        # APPROVED
        if tool_execution_id:
            execution = self.db.get(ToolExecution, tool_execution_id)
            if execution is not None:
                execution.status = ToolExecutionStatus.APPROVED
                self.db.commit()
            return {
                "tool_status": ToolExecutionStatus.APPROVED,
                "status": WorkflowStatus.VERIFYING,
                "resolved_by_human": True,
            }

        return {"status": WorkflowStatus.PLANNED, "resolved_by_human": True}

    def respond(self, state: WorkflowState) -> dict[str, Any]:
        status = state["status"]
        parts: list[str] = []

        intent = state.get("intent")
        if intent is not None:
            parts.append(
                f"Classified as {intent.value} (confidence {state.get('confidence', 0.0):.0%})."
            )

        chunks = state.get("retrieved_chunks") or []
        if chunks:
            docs = sorted({c["document"] for c in chunks})
            parts.append(f"Relevant NovaTech policy: {', '.join(docs)}.")

        resolved_by_human = state.get("resolved_by_human", False)

        if status == WorkflowStatus.POLICY_RETRIEVED:
            status = WorkflowStatus.COMPLETED
            parts.append(
                "No automated action exists for this request type yet; the policy "
                "excerpts above should answer it, or route it to the relevant team."
            )
        elif status == WorkflowStatus.COMPLETED:
            parts.append(
                "Approved by a human reviewer and completed."
                if resolved_by_human
                else "Approved and completed automatically."
            )
        elif status == WorkflowStatus.REJECTED:
            parts.append(
                "Denied by a human reviewer."
                if resolved_by_human
                else "Denied under NovaTech policy."
            )
        elif status == WorkflowStatus.AWAITING_APPROVAL:
            reason = ", ".join(state.get("risk_flags") or []) or "the applicable policy tier"
            parts.append(f"Needs human approval before it can proceed ({reason}).")
        elif status == WorkflowStatus.FAILED:
            parts.append("Could not be completed automatically and needs manual follow-up.")

        return {"status": status, "final_response": " ".join(parts)}


def route_after_retrieve(state: WorkflowState) -> str:
    return "plan" if state["intent"] in TOOL_INTENTS else "respond"


def route_after_risk_check(state: WorkflowState) -> str:
    return "respond" if state["escalate"] else "execute"


def route_after_execute(state: WorkflowState) -> str:
    return "verify" if state["tool_status"] == ToolExecutionStatus.APPROVED else "respond"


def route_after_decision(state: WorkflowState) -> str:
    if state["status"] == WorkflowStatus.REJECTED:
        return "respond"
    if state["status"] == WorkflowStatus.VERIFYING:
        return "verify"
    return "execute"
