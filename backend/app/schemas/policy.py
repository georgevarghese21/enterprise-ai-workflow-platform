from pydantic import BaseModel, ConfigDict, Field


class PolicyChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_name: str
    title: str | None
    chunk_index: int
    content: str


class PolicySearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class PolicySearchResult(BaseModel):
    chunk: PolicyChunkRead
    score: float


class PolicyDocumentSummary(BaseModel):
    document_name: str
    chunk_count: int
