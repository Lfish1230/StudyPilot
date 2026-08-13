from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.interfaces import ChunkSink, EmbeddingClient
from app.ai.types import EmbeddingUnavailableError
from app.documents.chunker import chunk_pages
from app.documents.model import Document, DocumentStatus
from app.documents.parser import (
    InvalidPdfError,
    PdfPageLimitError,
    ScannedPdfError,
    parse_pdf,
)
from app.documents.storage import ObjectStorage


async def mark_document_failed(
    session_factory: async_sessionmaker[AsyncSession],
    document_id: UUID,
    failure_code: str,
    failure_message: str,
) -> None:
    async with session_factory() as session:
        document = await session.get(Document, document_id)
        if document is None:
            return
        document.status = DocumentStatus.FAILED
        document.failure_code = failure_code
        document.failure_message = failure_message
        document.processing_started_at = None
        await session.commit()


async def mark_document_ready(
    session_factory: async_sessionmaker[AsyncSession],
    document_id: UUID,
    page_count: int,
) -> None:
    async with session_factory() as session:
        document = await session.get(Document, document_id)
        if document is None:
            return
        document.status = DocumentStatus.READY
        document.page_count = page_count
        document.failure_code = None
        document.failure_message = None
        document.processing_started_at = None
        await session.commit()


async def process_document(
    document_id: UUID,
    session_factory: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    embedding_client: EmbeddingClient,
    chunk_sink: ChunkSink,
    max_pages: int = 300,
) -> None:
    async with session_factory() as session:
        document = await session.get(Document, document_id, with_for_update=True)
        if document is None:
            return
        document.status = DocumentStatus.PROCESSING
        document.processing_started_at = datetime.now(UTC)
        document.failure_code = None
        document.failure_message = None
        object_key = document.object_key
        course_id = document.course_id
        await session.commit()

    try:
        pdf_bytes = await storage.download(object_key)
        pages = parse_pdf(pdf_bytes, max_pages=max_pages)
        chunks = chunk_pages(pages, max_tokens=700, overlap_tokens=100)
        embeddings = await embedding_client.embed([chunk.content for chunk in chunks])
        if len(embeddings) != len(chunks):
            raise EmbeddingUnavailableError("embedding count mismatch")
        await chunk_sink.replace(document_id, course_id, chunks, embeddings)
    except ScannedPdfError:
        await mark_document_failed(
            session_factory,
            document_id,
            "scanned_pdf",
            "暂不支持扫描版 PDF。",
        )
        return
    except PdfPageLimitError:
        await mark_document_failed(
            session_factory,
            document_id,
            "pdf_page_limit_exceeded",
            f"PDF 页数不能超过 {max_pages} 页。",
        )
        return
    except InvalidPdfError:
        await mark_document_failed(
            session_factory,
            document_id,
            "invalid_pdf_content",
            "PDF 内容无法解析。",
        )
        return
    except EmbeddingUnavailableError:
        await mark_document_failed(
            session_factory,
            document_id,
            "embedding_unavailable",
            "文档向量化暂时失败，请稍后重试。",
        )
        return

    await mark_document_ready(session_factory, document_id, page_count=len(pages))
