from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.employee import Employee
from app.models.enums import WorkflowStatus
from app.models.request import Request
from app.models.workflow_event import WorkflowEvent
from app.schemas.request import ApprovalDecisionRequest, RequestCreate, RequestRead
from app.schemas.workflow_event import WorkflowEventRead
from app.services.audit import record_workflow_event
from app.services.llm_provider import get_llm_provider
from app.workflows.graph import run_request_resume, run_request_workflow

router = APIRouter(prefix="/api/requests", tags=["requests"])


@router.post("", response_model=RequestRead, status_code=201)
def create_request(payload: RequestCreate, db: Session = Depends(get_db)) -> Request:
    employee = db.get(Employee, payload.employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")

    request = Request(employee_id=payload.employee_id, raw_query=payload.raw_query)
    db.add(request)
    db.commit()
    db.refresh(request)

    record_workflow_event(
        db,
        request.id,
        "request_created",
        {"raw_query": request.raw_query},
        actor=f"employee:{request.employee_id}",
    )
    return request


@router.get("", response_model=list[RequestRead])
def list_requests(db: Session = Depends(get_db)) -> list[Request]:
    return list(db.scalars(select(Request).order_by(Request.created_at.desc())))


@router.get("/pending-approval", response_model=list[RequestRead])
def list_pending_approval_requests(db: Session = Depends(get_db)) -> list[Request]:
    """The human approval queue: every request currently sitting at
    AWAITING_APPROVAL, oldest first. Registered ahead of `/{request_id}`
    below so "pending-approval" isn't swallowed by that path parameter.
    """
    return list(
        db.scalars(
            select(Request)
            .where(Request.status == WorkflowStatus.AWAITING_APPROVAL)
            .order_by(Request.updated_at)
        )
    )


@router.get("/{request_id}", response_model=RequestRead)
def get_request(request_id: UUID, db: Session = Depends(get_db)) -> Request:
    request = db.get(Request, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return request


@router.get("/{request_id}/timeline", response_model=list[WorkflowEventRead])
def get_request_timeline(request_id: UUID, db: Session = Depends(get_db)) -> list[WorkflowEvent]:
    """The full audit trail for a request, oldest first: every workflow-graph
    node it passed through (one event per node, `event_type` = node name),
    plus `request_created` and `approval_decision` events logged directly by
    this API. See `app.services.audit` for how these get written.
    """
    if db.get(Request, request_id) is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return list(
        db.scalars(
            select(WorkflowEvent)
            .where(WorkflowEvent.request_id == request_id)
            .order_by(WorkflowEvent.created_at, WorkflowEvent.id)
        )
    )


@router.post("/{request_id}/classify", response_model=RequestRead)
def classify_request(request_id: UUID, db: Session = Depends(get_db)) -> Request:
    request = db.get(Request, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")

    provider = get_llm_provider()
    result = provider.classify(request.raw_query)

    request.intent = result.intent
    request.classification_confidence = result.confidence
    request.classification_reasoning = result.reasoning
    request.status = WorkflowStatus.CLASSIFIED
    db.commit()
    db.refresh(request)
    return request


@router.post("/{request_id}/run", response_model=RequestRead)
def run_request_workflow_endpoint(request_id: UUID, db: Session = Depends(get_db)) -> Request:
    """Run the full LangGraph workflow (Phase 5) for a request end to end.

    Unlike `/classify`, which only runs the classification step, this runs
    classify -> retrieve -> plan -> risk check -> execute -> respond in one
    call and persists every artifact the graph produced along the way.
    """
    request = db.get(Request, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")

    final_state = run_request_workflow(db, request)

    request.intent = final_state.get("intent")
    request.classification_confidence = final_state.get("confidence")
    request.classification_reasoning = final_state.get("reasoning")
    # Not `X or None`: the graph's initial state always seeds these as `[]`/`{}`
    # (see run_request_workflow), so a node that legitimately ran and found
    # nothing (e.g. a plan with zero extractable arguments) is a real `{}`,
    # not "this step never ran" - collapsing it to NULL broke templates that
    # call `.items()`/iterate on it downstream.
    request.retrieved_policy = final_state.get("retrieved_chunks")
    request.plan_tool_name = final_state.get("plan_tool_name")
    request.plan_arguments = final_state.get("plan_arguments")
    request.risk_level = final_state.get("risk_level")
    request.risk_flags = final_state.get("risk_flags")
    request.tool_execution_id = final_state.get("tool_execution_id")
    request.status = final_state["status"]
    request.final_response = final_state.get("final_response")
    db.commit()
    db.refresh(request)
    return request


def _resolve_approval(
    request_id: UUID, payload: ApprovalDecisionRequest, decision: str, db: Session
) -> Request:
    request = db.get(Request, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")
    if request.status != WorkflowStatus.AWAITING_APPROVAL:
        raise HTTPException(
            status_code=409,
            detail=f"Request is not awaiting approval (status={request.status.value})",
        )

    approver = db.get(Employee, payload.approver_employee_id)
    if approver is None:
        raise HTTPException(status_code=404, detail="Approver employee not found")
    if not approver.active:
        raise HTTPException(status_code=400, detail="Approver employee is not active")
    if approver.id == request.employee_id:
        raise HTTPException(
            status_code=400, detail="An employee cannot approve or reject their own request"
        )

    try:
        final_state = run_request_resume(db, request, decision)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    request.status = final_state["status"]
    request.final_response = final_state.get("final_response")
    if final_state.get("tool_execution_id"):
        request.tool_execution_id = final_state["tool_execution_id"]
    request.approver_employee_id = payload.approver_employee_id
    request.approval_notes = payload.notes
    request.approved_at = datetime.now(UTC)
    db.commit()
    db.refresh(request)

    record_workflow_event(
        db,
        request.id,
        "approval_decision",
        {"decision": decision, "notes": payload.notes},
        actor=f"employee:{payload.approver_employee_id}",
    )
    return request


@router.post("/{request_id}/approve", response_model=RequestRead)
def approve_request(
    request_id: UUID, payload: ApprovalDecisionRequest, db: Session = Depends(get_db)
) -> Request:
    """Approve a request sitting at AWAITING_APPROVAL and resume its workflow.

    Authorization here is deliberately minimal for this phase: any active
    employee other than the requester themselves can approve or reject -
    there's no real RBAC (e.g. "must be the requester's manager" or "must
    be Security for a HIGH-sensitivity resource") yet. A future phase could
    tighten this to check `approver.id == request.employee.manager_id` or a
    department match against the tool's own message (e.g. "Security
    co-approval" for a contractor's HIGH-sensitivity access).
    """
    return _resolve_approval(request_id, payload, "APPROVED", db)


@router.post("/{request_id}/reject", response_model=RequestRead)
def reject_request(
    request_id: UUID, payload: ApprovalDecisionRequest, db: Session = Depends(get_db)
) -> Request:
    return _resolve_approval(request_id, payload, "REJECTED", db)
