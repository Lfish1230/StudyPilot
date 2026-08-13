from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConversationCreate(BaseModel):
    """Reserved request body so the API can grow without changing the route."""


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    course_id: UUID
    created_at: datetime
    updated_at: datetime


class QuestionCreate(BaseModel):
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be blank")
        return normalized


class CitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_id: str
    document_id: UUID
    document_name: str
    page_number: int
    snippet: str


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    content: str
    refused: bool
    model: str | None
    input_tokens: int
    output_tokens: int
    latency_ms: int | None
    citations: list[CitationResponse]
    created_at: datetime
