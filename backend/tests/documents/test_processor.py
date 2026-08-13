from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.ai.types import EmbeddingUnavailableError
from app.core.database import SessionLocal
from app.documents.chunker import TextChunk
from app.documents.jobs import recover_stale_document_jobs
from app.documents.model import Document, DocumentStatus
from app.documents.processor import process_document
from app.documents.storage import FakeObjectStorage
from tests.conftest import CreatedUser


def make_pdf(text: str | None) -> bytes:
    pdf = pymupdf.open()
    page = pdf.new_page()
    if text:
        page.insert_text((72, 72), text)
    data = pdf.tobytes()
    pdf.close()
    return data


class FakeEmbeddingClient:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        if self.fail:
            raise EmbeddingUnavailableError
        return [[float(index), 1.0] for index, _text in enumerate(texts)]


class FakeChunkSink:
    def __init__(self) -> None:
        self.replacements: list[
            tuple[UUID, UUID, list[TextChunk], list[list[float]]]
        ] = []
        self.current: dict[UUID, list[TextChunk]] = {}

    async def replace(
        self,
        document_id: UUID,
        course_id: UUID,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
    ) -> None:
        self.current[document_id] = list(chunks)
        self.replacements.append((document_id, course_id, chunks, embeddings))


def create_uploaded_document(
    client: TestClient,
    headers: dict[str, str],
    pdf_data: bytes,
) -> UUID:
    course = client.post("/courses", json={"name": "人工智能"}, headers=headers)
    assert course.status_code == 201
    response = client.post(
        f"/courses/{course.json()['id']}/documents",
        headers=headers,
        files={"file": ("notes.pdf", pdf_data, "application/pdf")},
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


async def load_document(document_id: UUID) -> Document:
    async with SessionLocal() as session:
        document = await session.get(Document, document_id)
        assert document is not None
        return document


@pytest.mark.asyncio
async def test_processor_transitions_uploaded_to_ready_and_replaces_chunks(
    client: TestClient,
    auth_headers: dict[str, str],
    object_storage: FakeObjectStorage,
) -> None:
    document_id = create_uploaded_document(
        client, auth_headers, make_pdf("alpha beta gamma " * 500)
    )
    embedding_client = FakeEmbeddingClient()
    sink = FakeChunkSink()

    await process_document(
        document_id, SessionLocal, object_storage, embedding_client, sink
    )
    ready = await load_document(document_id)
    assert ready.status == DocumentStatus.READY
    assert ready.page_count == 1
    assert ready.processing_started_at is None
    assert sink.current[document_id]
    assert len(embedding_client.calls) == 1

    await process_document(
        document_id, SessionLocal, object_storage, embedding_client, sink
    )
    assert len(sink.replacements) == 2
    assert len(sink.current[document_id]) == len(sink.replacements[-1][2])


@pytest.mark.asyncio
async def test_processor_marks_scanned_pdf_failed(
    client: TestClient,
    auth_headers: dict[str, str],
    object_storage: FakeObjectStorage,
) -> None:
    document_id = create_uploaded_document(client, auth_headers, make_pdf(None))
    await process_document(
        document_id,
        SessionLocal,
        object_storage,
        FakeEmbeddingClient(),
        FakeChunkSink(),
    )
    failed = await load_document(document_id)
    assert failed.status == DocumentStatus.FAILED
    assert failed.failure_code == "scanned_pdf"
    assert failed.failure_message == "暂不支持扫描版 PDF。"


@pytest.mark.asyncio
async def test_processor_sanitizes_embedding_failure(
    client: TestClient,
    auth_headers: dict[str, str],
    object_storage: FakeObjectStorage,
) -> None:
    document_id = create_uploaded_document(
        client, auth_headers, make_pdf("useful text")
    )
    await process_document(
        document_id,
        SessionLocal,
        object_storage,
        FakeEmbeddingClient(fail=True),
        FakeChunkSink(),
    )
    failed = await load_document(document_id)
    assert failed.status == DocumentStatus.FAILED
    assert failed.failure_code == "embedding_unavailable"
    assert failed.failure_message == "文档向量化暂时失败，请稍后重试。"


@pytest.mark.asyncio
async def test_recovery_marks_exact_cutoff_and_older_jobs_failed(
    client: TestClient,
    user_factory: Callable[..., CreatedUser],
    token_for: Callable[[CreatedUser], dict[str, str]],
    object_storage: FakeObjectStorage,
) -> None:
    del object_storage
    headers = token_for(user_factory())
    ids = [
        create_uploaded_document(client, headers, make_pdf(f"document {index}"))
        for index in range(3)
    ]
    now = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
    timestamps = [
        now - timedelta(minutes=16),
        now - timedelta(minutes=15),
        now - timedelta(minutes=14, seconds=59),
    ]
    async with SessionLocal() as session:
        for document_id, started_at in zip(ids, timestamps, strict=True):
            await session.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(
                    status=DocumentStatus.PROCESSING,
                    processing_started_at=started_at,
                )
            )
        await session.commit()
        recovered = await recover_stale_document_jobs(
            session, cutoff_minutes=15, now=now
        )
    assert recovered == 2

    async with SessionLocal() as session:
        states = list(
            await session.scalars(
                select(Document.status)
                .where(Document.id.in_(ids))
                .order_by(Document.id)
            )
        )
    assert states.count(DocumentStatus.FAILED) == 2
    assert states.count(DocumentStatus.PROCESSING) == 1
