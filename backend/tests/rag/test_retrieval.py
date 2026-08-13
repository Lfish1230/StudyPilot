from collections.abc import Callable
from uuid import UUID

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.documents.chunker import TextChunk
from app.documents.model import Document, DocumentStatus
from app.documents.storage import FakeObjectStorage
from app.main import create_app
from app.rag.model import DocumentChunk
from app.rag.repository import (
    PgVectorChunkSink,
    get_document_context,
    retrieve_chunks,
)
from tests.conftest import CreatedUser


def unit_vector(index: int) -> list[float]:
    vector = [0.0] * 1024
    vector[index] = 1.0
    return vector


def text_pdf() -> bytes:
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "TCP uses a three way handshake.")
    data = pdf.tobytes()
    pdf.close()
    return data


class IntegrationEmbeddingClient:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [unit_vector(index % 2) for index, _text in enumerate(texts)]


def create_course_and_document(
    client: TestClient,
    headers: dict[str, str],
    course_name: str,
) -> tuple[UUID, UUID]:
    course = client.post("/courses", json={"name": course_name}, headers=headers)
    uploaded = client.post(
        f"/courses/{course.json()['id']}/documents",
        headers=headers,
        files={"file": ("notes.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
    )
    return UUID(course.json()["id"]), UUID(uploaded.json()["id"])


@pytest.mark.asyncio
async def test_retrieval_is_course_scoped_ordered_limited_and_thresholded(
    client: TestClient,
    user_factory: Callable[..., CreatedUser],
    token_for: Callable[[CreatedUser], dict[str, str]],
) -> None:
    user = user_factory()
    headers = token_for(user)
    course_a, document_a = create_course_and_document(client, headers, "课程 A")
    course_b, document_b = create_course_and_document(client, headers, "课程 B")
    sink = PgVectorChunkSink(SessionLocal)
    near = unit_vector(0)
    medium = [0.8, 0.6] + [0.0] * 1022
    far = unit_vector(1)
    await sink.replace(
        document_a,
        course_a,
        [
            TextChunk(1, "near", 1),
            TextChunk(2, "medium", 1),
            TextChunk(3, "far", 1),
        ],
        [near, medium, far],
    )
    await sink.replace(
        document_b,
        course_b,
        [TextChunk(1, "foreign", 1)],
        [near],
    )

    async with SessionLocal() as session:
        first_document = await session.get(Document, document_a)
        second_document = await session.get(Document, document_b)
        assert first_document is not None
        assert second_document is not None
        first_document.status = DocumentStatus.READY
        second_document.status = DocumentStatus.READY
        await session.commit()

    async with SessionLocal() as session:
        results = await retrieve_chunks(
            session, course_a, near, limit=5, max_distance=0.40
        )
    assert [result.content for result in results] == ["near", "medium"]
    assert [result.source_id for result in results] == ["S1", "S2"]
    assert all(result.document_id == document_a for result in results)
    assert results[0].distance <= results[1].distance <= 0.40


@pytest.mark.asyncio
async def test_retrieval_excludes_chunks_from_non_ready_documents(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    course_id, document_id = create_course_and_document(
        client, auth_headers, "处理中文档"
    )
    await PgVectorChunkSink(SessionLocal).replace(
        document_id,
        course_id,
        [TextChunk(1, "stale chunk", 2)],
        [unit_vector(0)],
    )

    async with SessionLocal() as session:
        results = await retrieve_chunks(session, course_id, unit_vector(0))

    assert results == []


@pytest.mark.asyncio
async def test_context_honors_document_filter_order_and_token_budget(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    course_id, document_id = create_course_and_document(
        client, auth_headers, "上下文课程"
    )
    sink = PgVectorChunkSink(SessionLocal)
    await sink.replace(
        document_id,
        course_id,
        [TextChunk(1, "one", 4), TextChunk(2, "two", 5)],
        [unit_vector(0), unit_vector(1)],
    )
    async with SessionLocal() as session:
        selected = await get_document_context(session, [document_id], token_budget=8)
        all_rows = list(await session.scalars(select(DocumentChunk)))
        document = await session.get(Document, document_id)
    assert document is not None
    assert len(all_rows) == 2
    assert [chunk.content for chunk in selected] == ["one"]


def test_upload_background_processing_reaches_ready_and_persists_chunks(
    object_storage: FakeObjectStorage,
) -> None:
    sink = PgVectorChunkSink(SessionLocal)
    app = create_app(
        object_storage=object_storage,
        embedding_client=IntegrationEmbeddingClient(),
        chunk_sink=sink,
    )
    with TestClient(app) as integration_client:
        registered = integration_client.post(
            "/auth/register",
            json={
                "email": "integration@example.com",
                "password": "correct-horse-42",
            },
        )
        assert registered.status_code == 201
        login = integration_client.post(
            "/auth/login",
            json={
                "email": "integration@example.com",
                "password": "correct-horse-42",
            },
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        course = integration_client.post(
            "/courses", json={"name": "网络"}, headers=headers
        )
        uploaded = integration_client.post(
            f"/courses/{course.json()['id']}/documents",
            headers=headers,
            files={"file": ("network.pdf", text_pdf(), "application/pdf")},
        )
        assert uploaded.status_code == 201
        document_id = UUID(uploaded.json()["id"])
        detail = integration_client.get(f"/documents/{document_id}", headers=headers)
        assert detail.json()["status"] == "ready"

    async def count_chunks() -> int:
        async with SessionLocal() as session:
            rows = list(
                await session.scalars(
                    select(DocumentChunk).where(
                        DocumentChunk.document_id == document_id
                    )
                )
            )
            return len(rows)

    import asyncio

    assert asyncio.run(count_chunks()) >= 1
