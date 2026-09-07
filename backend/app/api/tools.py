import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.employee import Employee
from app.models.request import Request
from app.models.resource import Resource
from app.models.tool_execution import ToolExecution
from app.schemas.tool import (
    DataAccessToolRequest,
    ExpenseToolRequest,
    ITTicketToolRequest,
    ToolExecutionRead,
    TravelBookingToolRequest,
)
from app.tools.data_access import grant_data_access
from app.tools.expense import submit_expense
from app.tools.it_ticket import create_it_ticket
from app.tools.result import ToolResult
from app.tools.travel import book_travel

router = APIRouter(prefix="/api/tools", tags=["tools"])


def _get_employee(db: Session, employee_id: int) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


def _check_request_exists(db: Session, request_id: uuid.UUID | None) -> None:
    if request_id is not None and db.get(Request, request_id) is None:
        raise HTTPException(status_code=404, detail="Request not found")


def _persist(
    db: Session,
    tool_name: str,
    employee_id: int,
    request_id: uuid.UUID | None,
    input_payload: dict,
    result: ToolResult,
) -> ToolExecution:
    execution = ToolExecution(
        request_id=request_id,
        employee_id=employee_id,
        tool_name=tool_name,
        status=result.status,
        input_payload=input_payload,
        result_payload=result.details,
        message=result.message,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


@router.post("/data-access", response_model=ToolExecutionRead, status_code=201)
def data_access_tool(
    payload: DataAccessToolRequest, db: Session = Depends(get_db)
) -> ToolExecution:
    employee = _get_employee(db, payload.employee_id)
    _check_request_exists(db, payload.request_id)
    resource = db.scalar(select(Resource).where(Resource.name == payload.resource_name))
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found")

    result = grant_data_access(employee, resource, payload.duration_days)
    return _persist(
        db,
        "grant_data_access",
        employee.id,
        payload.request_id,
        payload.model_dump(mode="json"),
        result,
    )


@router.post("/it-ticket", response_model=ToolExecutionRead, status_code=201)
def it_ticket_tool(payload: ITTicketToolRequest, db: Session = Depends(get_db)) -> ToolExecution:
    employee = _get_employee(db, payload.employee_id)
    _check_request_exists(db, payload.request_id)

    result = create_it_ticket(
        employee, payload.category, payload.description, payload.equipment_cost_usd
    )
    return _persist(
        db,
        "create_it_ticket",
        employee.id,
        payload.request_id,
        payload.model_dump(mode="json"),
        result,
    )


@router.post("/travel-booking", response_model=ToolExecutionRead, status_code=201)
def travel_booking_tool(
    payload: TravelBookingToolRequest, db: Session = Depends(get_db)
) -> ToolExecution:
    employee = _get_employee(db, payload.employee_id)
    _check_request_exists(db, payload.request_id)

    result = book_travel(
        employee, payload.destination, payload.is_international, payload.total_cost_usd
    )
    return _persist(
        db,
        "book_travel",
        employee.id,
        payload.request_id,
        payload.model_dump(mode="json"),
        result,
    )


@router.post("/expense-reimbursement", response_model=ToolExecutionRead, status_code=201)
def expense_reimbursement_tool(
    payload: ExpenseToolRequest, db: Session = Depends(get_db)
) -> ToolExecution:
    employee = _get_employee(db, payload.employee_id)
    _check_request_exists(db, payload.request_id)

    result = submit_expense(employee, payload.amount_usd, payload.description)
    return _persist(
        db,
        "submit_expense",
        employee.id,
        payload.request_id,
        payload.model_dump(mode="json"),
        result,
    )


@router.get("/executions", response_model=list[ToolExecutionRead])
def list_tool_executions(db: Session = Depends(get_db)) -> list[ToolExecution]:
    return list(db.scalars(select(ToolExecution).order_by(ToolExecution.created_at.desc())))
