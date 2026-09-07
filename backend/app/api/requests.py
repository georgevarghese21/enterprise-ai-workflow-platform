from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.employee import Employee
from app.models.enums import WorkflowStatus
from app.models.request import Request
from app.schemas.request import RequestCreate, RequestRead
from app.services.llm_provider import get_llm_provider

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
    return request


@router.get("", response_model=list[RequestRead])
def list_requests(db: Session = Depends(get_db)) -> list[Request]:
    return list(db.scalars(select(Request).order_by(Request.created_at.desc())))


@router.get("/{request_id}", response_model=RequestRead)
def get_request(request_id: UUID, db: Session = Depends(get_db)) -> Request:
    request = db.get(Request, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return request


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
