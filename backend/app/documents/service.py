from datetime import UTC, datetime, time
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ApiError, NotFoundError
from app.courses.model import Course
from app.courses.service import get_owned_course
from app.documents.model import Document, DocumentStatus
from app.documents.storage import ObjectStorage


async def read_valid_pdf(
    data: bytes, content_type: str | None, settings: Settings
) -> None:
    if content_type != "application/pdf":
        raise ApiError(415, "invalid_pdf_type", "仅支持 PDF 文件。")
    if len(data) > settings.max_pdf_bytes:
        raise ApiError(413, "pdf_too_large", "PDF 文件不能超过 20 MB。")
    if not data.startswith(b"%PDF-"):
        raise ApiError(422, "invalid_pdf_content", "文件内容不是有效的 PDF。")


async def enforce_daily_upload_quota(
    session: AsyncSession, owner_id: UUID, settings: Settings
) -> None:
    start = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
    uploaded_count = await session.scalar(
        select(func.count(Document.id))
        .join(Course, Course.id == Document.course_id)
        .where(Course.owner_id == owner_id, Document.created_at >= start)
    )
    if int(uploaded_count or 0) >= settings.daily_upload_quota:
        raise ApiError(
            429,
            "upload_quota_exceeded",
            "今天的 PDF 上传次数已用完，请明天再试。",
        )


async def create_document(
    session: AsyncSession,
    storage: ObjectStorage,
    settings: Settings,
    owner_id: UUID,
    course_id: UUID,
    original_name: str,
    data: bytes,
    content_type: str | None,
) -> Document:
    await get_owned_course(session, owner_id, course_id)
    await read_valid_pdf(data, content_type, settings)
    await enforce_daily_upload_quota(session, owner_id, settings)

    document_id = uuid4()
    object_key = f"{owner_id}/{course_id}/{document_id}.pdf"
    await storage.upload(object_key, data, "application/pdf")

    document = Document(
        id=document_id,
        course_id=course_id,
        original_name=(original_name or "document.pdf")[:255],
        object_key=object_key,
        size_bytes=len(data),
        status=DocumentStatus.UPLOADED,
    )
    session.add(document)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        await storage.delete(object_key)
        raise
    await session.refresh(document)
    return document


async def get_owned_document(
    session: AsyncSession, owner_id: UUID, document_id: UUID
) -> Document:
    document = await session.scalar(
        select(Document)
        .join(Course, Course.id == Document.course_id)
        .where(Document.id == document_id, Course.owner_id == owner_id)
    )
    if document is None:
        raise NotFoundError("document_not_found", "文档不存在。")
    return document


async def list_course_documents(
    session: AsyncSession, owner_id: UUID, course_id: UUID
) -> list[Document]:
    await get_owned_course(session, owner_id, course_id)
    documents = await session.scalars(
        select(Document)
        .where(Document.course_id == course_id)
        .order_by(Document.created_at.desc(), Document.id.desc())
    )
    return list(documents)


async def delete_document(
    session: AsyncSession, storage: ObjectStorage, document: Document
) -> None:
    await storage.delete(document.object_key)
    await session.delete(document)
    await session.commit()


async def prepare_document_retry(session: AsyncSession, document: Document) -> Document:
    if document.status != DocumentStatus.FAILED:
        raise ApiError(409, "document_not_failed", "只有处理失败的文档可以重试。")
    document.status = DocumentStatus.UPLOADED
    document.failure_code = None
    document.failure_message = None
    document.processing_started_at = None
    await session.commit()
    await session.refresh(document)
    return document
