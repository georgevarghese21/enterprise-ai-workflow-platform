"""Server-rendered HTML frontend (Phase 8): Jinja2 templates + htmx.

Deliberately not a JSON API client - these routes talk to the same
services/models the JSON API under `app.api.*` uses (DB session, the
workflow graphs, `record_workflow_event`) directly, rather than making an
HTTP call to `app.api.requests` from here. `POST` actions that htmx drives
(`/run`, `/approve`, `/reject`) return a rendered HTML fragment rather than
a redirect, so htmx can swap just the part of the page that changed.
"""

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.requests import Request as StarletteRequest
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.employee import Employee
from app.models.enums import WorkflowStatus
from app.models.request import Request as RequestModel
from app.models.resource import Resource
from app.models.tool_execution import ToolExecution
from app.models.workflow_event import WorkflowEvent
from app.services.audit import record_workflow_event
from app.workflows.graph import run_request_resume, run_request_workflow

router = APIRouter(tags=["web"])

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

_BADGE_CLASSES = {
    "COMPLETED": "ok",
    "APPROVED": "ok",
    "REJECTED": "danger",
    "DENIED": "danger",
    "FAILED": "danger",
    "AWAITING_APPROVAL": "warn",
    "PENDING_APPROVAL": "warn",
}
_SEVERITY_CLASSES = {"LOW": "ok", "MEDIUM": "warn", "HIGH": "danger"}


def _badge_class(status: Any) -> str:
    value = status.value if hasattr(status, "value") else status
    return _BADGE_CLASSES.get(value, "neutral")


def _severity_class(level: Any) -> str:
    value = level.value if hasattr(level, "value") else level
    return _SEVERITY_CLASSES.get(value, "neutral")


def _format_dt(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%Y-%m-%d %H:%M UTC")


templates.env.filters["badge"] = _badge_class
templates.env.filters["severity_badge"] = _severity_class
templates.env.filters["dt"] = _format_dt


def _active_employees(db: Session) -> list[Employee]:
    query = select(Employee).where(Employee.active.is_(True)).order_by(Employee.name)
    return list(db.scalars(query))


def _timeline_for(db: Session, request_id: uuid.UUID) -> list[WorkflowEvent]:
    return list(
        db.scalars(
            select(WorkflowEvent)
            .where(WorkflowEvent.request_id == request_id)
            .order_by(WorkflowEvent.created_at, WorkflowEvent.id)
        )
    )


def _request_card_context(
    db: Session, req: RequestModel, error: str | None = None
) -> dict[str, Any]:
    tool_execution = db.get(ToolExecution, req.tool_execution_id) if req.tool_execution_id else None
    approver_employee = (
        db.get(Employee, req.approver_employee_id) if req.approver_employee_id else None
    )
    approvers = [e for e in _active_employees(db) if e.id != req.employee_id]
    return {
        "req": req,
        "tool_execution": tool_execution,
        "approver_employee": approver_employee,
        "approvers": approvers,
        "timeline": _timeline_for(db, req.id),
        "error": error,
    }


def _get_request_or_404(db: Session, request_id: uuid.UUID) -> RequestModel:
    req = db.get(RequestModel, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return req


@router.get("/", response_class=HTMLResponse)
def dashboard(http_request: StarletteRequest, db: Session = Depends(get_db)) -> HTMLResponse:
    recent_query = select(RequestModel).order_by(RequestModel.created_at.desc()).limit(15)
    recent = list(db.scalars(recent_query))
    pending_query = select(RequestModel.id).where(
        RequestModel.status == WorkflowStatus.AWAITING_APPROVAL
    )
    pending = list(db.scalars(pending_query))
    total = len(list(db.scalars(select(RequestModel.id))))
    return templates.TemplateResponse(
        request=http_request,
        name="dashboard.html",
        context={"recent_requests": recent, "pending_count": len(pending), "total_count": total},
    )


@router.get("/requests", response_class=HTMLResponse)
def requests_list(
    http_request: StarletteRequest, status: str | None = None, db: Session = Depends(get_db)
) -> HTMLResponse:
    query = select(RequestModel).order_by(RequestModel.created_at.desc())
    if status:
        try:
            query = query.where(RequestModel.status == WorkflowStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail="Unknown status") from None
    return templates.TemplateResponse(
        request=http_request,
        name="requests_list.html",
        context={
            "requests_list": list(db.scalars(query)),
            "statuses": [s.value for s in WorkflowStatus],
            "status_filter": status or "",
        },
    )


@router.get("/requests/new", response_class=HTMLResponse)
def new_request_form(http_request: StarletteRequest, db: Session = Depends(get_db)) -> HTMLResponse:
    return templates.TemplateResponse(
        request=http_request, name="request_new.html", context={"employees": _active_employees(db)}
    )


@router.post("/requests")
def create_request_web(
    employee_id: int = Form(...), raw_query: str = Form(...), db: Session = Depends(get_db)
) -> RedirectResponse:
    if db.get(Employee, employee_id) is None:
        raise HTTPException(status_code=404, detail="Employee not found")

    req = RequestModel(employee_id=employee_id, raw_query=raw_query)
    db.add(req)
    db.commit()
    db.refresh(req)

    record_workflow_event(
        db, req.id, "request_created", {"raw_query": req.raw_query}, actor=f"employee:{employee_id}"
    )
    return RedirectResponse(url=f"/requests/{req.id}", status_code=303)


@router.get("/requests/{request_id}", response_class=HTMLResponse)
def request_detail(
    http_request: StarletteRequest, request_id: uuid.UUID, db: Session = Depends(get_db)
) -> HTMLResponse:
    req = _get_request_or_404(db, request_id)
    return templates.TemplateResponse(
        request=http_request, name="request_detail.html", context=_request_card_context(db, req)
    )


@router.post("/requests/{request_id}/run", response_class=HTMLResponse)
def run_request_web(
    http_request: StarletteRequest, request_id: uuid.UUID, db: Session = Depends(get_db)
) -> HTMLResponse:
    req = _get_request_or_404(db, request_id)

    final_state = run_request_workflow(db, req)
    req.intent = final_state.get("intent")
    req.classification_confidence = final_state.get("confidence")
    req.classification_reasoning = final_state.get("reasoning")
    # See the matching comment in app.api.requests.run_request_workflow_endpoint:
    # not `X or None`, since the graph's initial state seeds these as `[]`/`{}`.
    req.retrieved_policy = final_state.get("retrieved_chunks")
    req.plan_tool_name = final_state.get("plan_tool_name")
    req.plan_arguments = final_state.get("plan_arguments")
    req.risk_level = final_state.get("risk_level")
    req.risk_flags = final_state.get("risk_flags")
    req.tool_execution_id = final_state.get("tool_execution_id")
    req.status = final_state["status"]
    req.final_response = final_state.get("final_response")
    db.commit()
    db.refresh(req)

    return templates.TemplateResponse(
        request=http_request,
        name="partials/_request_card.html",
        context=_request_card_context(db, req),
    )


def _resolve_approval_web(
    http_request: StarletteRequest,
    request_id: uuid.UUID,
    decision: str,
    approver_employee_id: int,
    notes: str | None,
    view: str,
    db: Session,
) -> HTMLResponse:
    req = _get_request_or_404(db, request_id)
    if req.status != WorkflowStatus.AWAITING_APPROVAL:
        raise HTTPException(
            status_code=409, detail=f"Request is not awaiting approval (status={req.status.value})"
        )

    approver = db.get(Employee, approver_employee_id)
    if approver is None:
        raise HTTPException(status_code=404, detail="Approver employee not found")
    if not approver.active:
        raise HTTPException(status_code=400, detail="Approver employee is not active")
    if approver.id == req.employee_id:
        raise HTTPException(
            status_code=400, detail="An employee cannot approve or reject their own request"
        )

    try:
        final_state = run_request_resume(db, req, decision)
    except ValueError as exc:
        error = str(exc)
        if view == "queue":
            other_approvers = [e for e in _active_employees(db) if e.id != req.employee_id]
            return templates.TemplateResponse(
                request=http_request,
                name="partials/_approval_row.html",
                context={
                    "r": req,
                    "approvers_by_request": {req.id: other_approvers},
                    "error": error,
                },
            )
        return templates.TemplateResponse(
            request=http_request,
            name="partials/_request_card.html",
            context=_request_card_context(db, req, error=error),
        )

    req.status = final_state["status"]
    req.final_response = final_state.get("final_response")
    if final_state.get("tool_execution_id"):
        req.tool_execution_id = final_state["tool_execution_id"]
    req.approver_employee_id = approver_employee_id
    req.approval_notes = notes
    req.approved_at = datetime.now(UTC)
    db.commit()
    db.refresh(req)

    record_workflow_event(
        db,
        req.id,
        "approval_decision",
        {"decision": decision, "notes": notes},
        actor=f"employee:{approver_employee_id}",
    )

    if view == "queue":
        return templates.TemplateResponse(
            request=http_request,
            name="partials/_approval_row_result.html",
            context={"req": req, "approver_employee": approver},
        )
    return templates.TemplateResponse(
        request=http_request,
        name="partials/_request_card.html",
        context=_request_card_context(db, req),
    )


@router.post("/requests/{request_id}/approve", response_class=HTMLResponse)
def approve_request_web(
    http_request: StarletteRequest,
    request_id: uuid.UUID,
    approver_employee_id: int = Form(...),
    notes: str | None = Form(None),
    view: str = "card",
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return _resolve_approval_web(
        http_request, request_id, "APPROVED", approver_employee_id, notes, view, db
    )


@router.post("/requests/{request_id}/reject", response_class=HTMLResponse)
def reject_request_web(
    http_request: StarletteRequest,
    request_id: uuid.UUID,
    approver_employee_id: int = Form(...),
    notes: str | None = Form(None),
    view: str = "card",
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return _resolve_approval_web(
        http_request, request_id, "REJECTED", approver_employee_id, notes, view, db
    )


@router.get("/approvals", response_class=HTMLResponse)
def approvals_queue(http_request: StarletteRequest, db: Session = Depends(get_db)) -> HTMLResponse:
    pending = list(
        db.scalars(
            select(RequestModel)
            .where(RequestModel.status == WorkflowStatus.AWAITING_APPROVAL)
            .order_by(RequestModel.updated_at)
        )
    )
    active = _active_employees(db)
    approvers_by_request = {r.id: [e for e in active if e.id != r.employee_id] for r in pending}
    return templates.TemplateResponse(
        request=http_request,
        name="approvals.html",
        context={"pending": pending, "approvers_by_request": approvers_by_request},
    )


@router.get("/employees", response_class=HTMLResponse)
def employees_page(http_request: StarletteRequest, db: Session = Depends(get_db)) -> HTMLResponse:
    employees = list(db.scalars(select(Employee).order_by(Employee.id)))
    return templates.TemplateResponse(
        request=http_request, name="employees.html", context={"employees": employees}
    )


@router.get("/resources", response_class=HTMLResponse)
def resources_page(http_request: StarletteRequest, db: Session = Depends(get_db)) -> HTMLResponse:
    resources = list(db.scalars(select(Resource).order_by(Resource.name)))
    return templates.TemplateResponse(
        request=http_request, name="resources.html", context={"resources": resources}
    )
