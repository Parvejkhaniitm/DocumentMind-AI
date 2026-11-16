from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str | None) -> str | None:
        return value.strip() if value else value


class QuestionCreate(BaseModel):
    content: str = Field(min_length=2, max_length=2000)

    @field_validator("content", mode="before")
    @classmethod
    def clean_content(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
        if value == "":
            raise ValueError("Question cannot be blank.")
        return value


class ConversationRead(BaseModel):
    id: UUID
    workspace_id: UUID
    title: str
    created_at: datetime


class CitationRead(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_name: str
    page_number: int | None
    source_index: int
    relevance_score: float


class MessageRead(BaseModel):
    id: UUID
    role: str
    content: str
    answer_status: str | None
    created_at: datetime
    sources: list[CitationRead] = Field(default_factory=list)


class ConversationDetail(ConversationRead):
    messages: list[MessageRead]


class AnswerRead(MessageRead):
    pass
