from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.policy_chunk import PolicyChunk
from app.rag.retrieve import search_policy_chunks
from app.schemas.policy import PolicyDocumentSummary, PolicySearchRequest, PolicySearchResult

router = APIRouter(prefix="/api/policy", tags=["policy"])


@router.post("/search", response_model=list[PolicySearchResult])
def search_policy(
    payload: PolicySearchRequest, db: Session = Depends(get_db)
) -> list[PolicySearchResult]:
    results = search_policy_chunks(db, payload.query, payload.top_k)
    return [PolicySearchResult(chunk=r.chunk, score=r.score) for r in results]


@router.get("/documents", response_model=list[PolicyDocumentSummary])
def list_policy_documents(db: Session = Depends(get_db)) -> list[PolicyDocumentSummary]:
    rows = db.execute(
        select(PolicyChunk.document_name, func.count(PolicyChunk.id))
        .group_by(PolicyChunk.document_name)
        .order_by(PolicyChunk.document_name)
    ).all()
    return [
        PolicyDocumentSummary(document_name=name, chunk_count=count) for name, count in rows
    ]
