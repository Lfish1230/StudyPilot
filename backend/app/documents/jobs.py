from datetime import UTC, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.documents.model import Document, DocumentStatus


async def recover_stale_document_jobs(
    session: AsyncSession,
    cutoff_minutes: int = 15,
    now: datetime | None = None,
) -> int:
    current_time = now or datetime.now(UTC)
    cutoff = current_time - timedelta(minutes=cutoff_minutes)
    result = await session.execute(
        update(Document)
        .where(
            Document.status == DocumentStatus.PROCESSING,
            Document.processing_started_at <= cutoff,
        )
        .values(
            status=DocumentStatus.FAILED,
            failure_code="processing_interrupted",
            failure_message="文档处理被中断，请重试。",
            processing_started_at=None,
        )
    )
    await session.commit()
    return int(result.rowcount)  # type: ignore[attr-defined]
