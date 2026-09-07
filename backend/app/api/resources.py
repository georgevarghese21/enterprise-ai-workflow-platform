from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.resource import Resource
from app.schemas.resource import ResourceRead

router = APIRouter(prefix="/api/resources", tags=["resources"])


@router.get("", response_model=list[ResourceRead])
def list_resources(db: Session = Depends(get_db)) -> list[Resource]:
    return list(db.scalars(select(Resource).order_by(Resource.id)))
