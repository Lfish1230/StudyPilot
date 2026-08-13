import asyncio
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.ai.types import ChatMessage, ChatResult, TokenUsage
from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.documents.model import Document, DocumentStatus
from app.documents.storage import FakeObjectStorage
from app.main import create_app
from app.rag.model import DocumentChunk
from tests.conftest import CreatedUser


class FixedEmbeddingClient:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * 1023 for _ in texts]


class FixedChatClient:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(
        self,
        messages: list[ChatMessage],
        response_format: dict[str, object] | None = None,
    ) -> ChatResult:
        del messages, response_format
        self.calls += 1
        return ChatResult(
            content="TCP 三次握手用于确认双方的收发能力。[S1]",
            model="fake-chat",
            usage=TokenUsage(input_tokens=30, output_tokens=12),
        )


@pytest.fixture
def rag_client(object_storage: FakeObjectStorage) -> Iterator[TestClient]:
    async def scheduler(_document_id: UUID) -> None:
        return None

    app = create_app(
        object_storage=object_storage,
        document_scheduler=scheduler,
        embedding_client=FixedEmbeddingClient(),
        chat_client=FixedChatClient(),
    )
    with TestClient(app) as test_client:
        yield test_client


def register_and_headers(client: TestClient) -> tuple[CreatedUser, dict[str, str]]:
    password = "correct-horse-42"
    email = f"rag-{uuid4()}@example.com"
    registration = client.post(
        "/auth/register", json={"email": email, "password": password}
    )
    user = CreatedUser(registration.json()["id"], email, password)
    login = client.post("/auth/login", json={"email": email, "password": password})
    return user, {"Authorization": f"Bearer {login.json()['access_token']}"}


def create_course(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post("/courses", json={"name": "计算机网络"}, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


async def seed_document(course_id: str, *, ready: bool = True) -> UUID:
    document_id = uuid4()
    async with SessionLocal() as session:
        document = Document(
            id=document_id,
            course_id=UUID(course_id),
            original_name="计算机网络.pdf",
            object_key=f"tests/{document_id}.pdf",
            size_bytes=100,
            page_count=2,
            status=DocumentStatus.READY if ready else DocumentStatus.PROCESSING,
        )
        session.add(document)
        if ready:
            session.add(
                DocumentChunk(
                    document_id=document_id,
                    course_id=UUID(course_id),
                    page_number=2,
                    content="TCP 三次握手可以确认通信双方的收发能力。",
                    token_count=18,
                    embedding=[1.0] + [0.0] * 1023,
                )
            )
        await session.commit()
    return document_id


def test_conversation_crud_saves_grounded_messages_and_citations(
    rag_client: TestClient,
) -> None:
    _, headers = register_and_headers(rag_client)
    course_id = create_course(rag_client, headers)
    document_id = asyncio.run(seed_document(course_id))

    created = rag_client.post(f"/courses/{course_id}/conversations", headers=headers)
    assert created.status_code == 201
    conversation_id = created.json()["id"]

    listed = rag_client.get(f"/courses/{course_id}/conversations", headers=headers)
    assert [item["id"] for item in listed.json()] == [conversation_id]

    answer = rag_client.post(
        f"/conversations/{conversation_id}/messages",
        json={"question": "TCP 为什么需要三次握手？"},
        headers=headers,
    )
    assert answer.status_code == 201
    payload = answer.json()
    assert payload["role"] == "assistant"
    assert payload["model"] == "fake-chat"
    assert payload["input_tokens"] == 30
    assert payload["citations"] == [
        {
            "source_id": "S1",
            "document_id": str(document_id),
            "document_name": "计算机网络.pdf",
            "page_number": 2,
            "snippet": "TCP 三次握手可以确认通信双方的收发能力。",
        }
    ]

    history = rag_client.get(
        f"/conversations/{conversation_id}/messages", headers=headers
    )
    assert history.status_code == 200
    assert [message["role"] for message in history.json()] == ["user", "assistant"]
    assert history.json()[0]["content"] == "TCP 为什么需要三次握手？"


def test_conversations_hide_foreign_resources(rag_client: TestClient) -> None:
    _, alice_headers = register_and_headers(rag_client)
    _, bob_headers = register_and_headers(rag_client)
    course_id = create_course(rag_client, alice_headers)
    conversation_id = rag_client.post(
        f"/courses/{course_id}/conversations", headers=alice_headers
    ).json()["id"]

    foreign_list = rag_client.get(
        f"/courses/{course_id}/conversations", headers=bob_headers
    )
    foreign_history = rag_client.get(
        f"/conversations/{conversation_id}/messages", headers=bob_headers
    )
    foreign_send = rag_client.post(
        f"/conversations/{conversation_id}/messages",
        json={"question": "问题"},
        headers=bob_headers,
    )
    assert foreign_list.status_code == 404
    assert foreign_history.status_code == 404
    assert foreign_send.status_code == 404


def test_question_requires_a_ready_document(rag_client: TestClient) -> None:
    _, headers = register_and_headers(rag_client)
    course_id = create_course(rag_client, headers)
    asyncio.run(seed_document(course_id, ready=False))
    conversation_id = rag_client.post(
        f"/courses/{course_id}/conversations", headers=headers
    ).json()["id"]

    response = rag_client.post(
        f"/conversations/{conversation_id}/messages",
        json={"question": "问题"},
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["code"] == "document_not_ready"


def test_daily_question_quota_is_enforced_before_model_call(
    object_storage: FakeObjectStorage,
) -> None:
    chat = FixedChatClient()

    async def scheduler(_document_id: UUID) -> None:
        return None

    app = create_app(
        object_storage=object_storage,
        document_scheduler=scheduler,
        embedding_client=FixedEmbeddingClient(),
        chat_client=chat,
    )
    app.dependency_overrides[get_settings] = lambda: Settings(daily_question_quota=1)
    with TestClient(app) as client:
        _, headers = register_and_headers(client)
        course_id = create_course(client, headers)
        asyncio.run(seed_document(course_id))
        conversation_id = client.post(
            f"/courses/{course_id}/conversations", headers=headers
        ).json()["id"]
        endpoint = f"/conversations/{conversation_id}/messages"
        first = client.post(endpoint, json={"question": "第一次"}, headers=headers)
        second = client.post(endpoint, json={"question": "第二次"}, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 429
    assert second.json()["code"] == "question_quota_exceeded"
    assert chat.calls == 1


def test_empty_question_uses_stable_validation_error(rag_client: TestClient) -> None:
    _, headers = register_and_headers(rag_client)
    course_id = create_course(rag_client, headers)
    conversation_id = rag_client.post(
        f"/courses/{course_id}/conversations", headers=headers
    ).json()["id"]
    response = rag_client.post(
        f"/conversations/{conversation_id}/messages",
        json={"question": "   "},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
