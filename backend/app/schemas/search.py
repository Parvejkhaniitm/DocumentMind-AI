from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    document_ids: list[UUID] | None = Field(default=None, max_length=50)
    limit: int = Field(default=10, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Search query cannot be blank.")
        return value


class SearchResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_name: str
    source_index: int
    page_number: int | None
    content: str
    score: float


class SearchResponse(BaseModel):
    query: str
    items: list[SearchResult]
