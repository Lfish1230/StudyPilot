from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.documents.model import DocumentStatus


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    course_id: UUID
    original_name: str
    size_bytes: int
    page_count: int | None
    status: DocumentStatus
    failure_code: str | None
    failure_message: str | None
    created_at: datetime
    updated_at: datetime
