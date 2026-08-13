import asyncio
import json
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.ai.types import ChatMessage, ChatResult, TokenUsage
from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.documents.model import Document, DocumentStatus
from app.documents.storage import FakeObjectStorage
from app.main import create_app
from app.quizzes.models import Question
from app.rag.model import DocumentChunk
from tests.conftest import CreatedUser


class QuizChatClient:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(
        self,
        messages: list[ChatMessage],
        response_format: dict[str, object] | None = None,
    ) -> ChatResult:
        del response_format
        self.calls += 1
        request = json.loads(messages[1].content)
        source = request["SOURCE_DATA"][0]
        questions: list[dict[str, object]] = []
        for index in range(request["multiple_choice_count"]):
            questions.append(
                {
                    "type": "multiple_choice",
                    "prompt": f"选择题 {index + 1}",
                    "options": ["A", "B", "C", "D"],
                    "standard_answer": "A",
                    "explanation": "依据资料。",
                    "knowledge_point": "TCP",
                    "difficulty": "easy",
                    "source_document_id": source["document_id"],
                    "source_page": source["page_number"],
                }
            )
        for index in range(request["short_answer_count"]):
            questions.append(
                {
                    "type": "short_answer",
                    "prompt": f"简答题 {index + 1}",
                    "standard_answer": "确认双方能力。",
                    "rubric_points": ["发送能力", "接收能力"],
                    "explanation": "依据资料。",
                    "knowledge_point": "TCP",
                    "difficulty": "medium",
                    "source_document_id": source["document_id"],
                    "source_page": source["page_number"],
                }
            )
        return ChatResult(
            content=json.dumps({"title": "网络测验", "questions": questions}),
            model="fake-quiz-model",
            usage=TokenUsage(40, 20),
        )


class InvalidQuizChatClient:
    async def complete(
        self,
        messages: list[ChatMessage],
        response_format: dict[str, object] | None = None,
    ) -> ChatResult:
        del messages, response_format
        return ChatResult(
            content="invalid",
            model="fake-quiz-model",
            usage=TokenUsage(1, 1),
        )


class NoopEmbeddingClient:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * 1023 for _ in texts]


@pytest.fixture
def quiz_client(object_storage: FakeObjectStorage) -> Iterator[TestClient]:
    async def scheduler(_document_id: UUID) -> None:
        return None

    app = create_app(
        object_storage=object_storage,
        document_scheduler=scheduler,
        embedding_client=NoopEmbeddingClient(),
        chat_client=QuizChatClient(),
    )
    with TestClient(app) as client:
        yield client


def register(client: TestClient) -> tuple[CreatedUser, dict[str, str]]:
    password = "correct-horse-42"
    email = f"quiz-{uuid4()}@example.com"
    response = client.post(
        "/auth/register", json={"email": email, "password": password}
    )
    user = CreatedUser(response.json()["id"], email, password)
    login = client.post("/auth/login", json={"email": email, "password": password})
    return user, {"Authorization": f"Bearer {login.json()['access_token']}"}


def create_course(client: TestClient, headers: dict[str, str]) -> str:
    return client.post("/courses", json={"name": "计算机网络"}, headers=headers).json()[
        "id"
    ]


async def seed_document(course_id: str, *, ready: bool = True) -> UUID:
    document_id = uuid4()
    async with SessionLocal() as session:
        session.add(
            Document(
                id=document_id,
                course_id=UUID(course_id),
                original_name="network.pdf",
                object_key=f"quiz/{document_id}.pdf",
                size_bytes=100,
                page_count=1,
                status=DocumentStatus.READY if ready else DocumentStatus.PROCESSING,
            )
        )
        if ready:
            session.add(
                DocumentChunk(
                    document_id=document_id,
                    course_id=UUID(course_id),
                    page_number=7,
                    content="TCP 三次握手用于确认双方的收发能力。",
                    token_count=20,
                    embedding=[1.0] + [0.0] * 1023,
                )
            )
        await session.commit()
    return document_id


def test_generate_list_and_get_quiz_hides_answers(quiz_client: TestClient) -> None:
    _, headers = register(quiz_client)
    course_id = create_course(quiz_client, headers)
    document_id = asyncio.run(seed_document(course_id))

    created = quiz_client.post(
        f"/courses/{course_id}/quizzes",
        json={
            "document_ids": [str(document_id)],
            "multiple_choice_count": 1,
            "short_answer_count": 1,
        },
        headers=headers,
    )
    assert created.status_code == 201
    payload = created.json()
    assert payload["title"] == "网络测验"
    assert payload["question_count"] == 2
    assert [question["type"] for question in payload["questions"]] == [
        "multiple_choice",
        "short_answer",
    ]
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "standard_answer" not in serialized
    assert "rubric_points" not in serialized
    assert "explanation" not in serialized

    listed = quiz_client.get(f"/courses/{course_id}/quizzes", headers=headers)
    detail = quiz_client.get(f"/quizzes/{payload['id']}", headers=headers)
    assert [item["id"] for item in listed.json()] == [payload["id"]]
    assert detail.json() == payload

    async def stored_answer() -> tuple[str, list[str] | None]:
        async with SessionLocal() as session:
            question = await session.scalar(
                select(Question).where(Question.quiz_id == UUID(payload["id"]))
            )
            assert question is not None
            return question.standard_answer, question.rubric_points

    standard_answer, _rubric = asyncio.run(stored_answer())
    assert standard_answer == "A"


def test_quiz_document_and_resource_ownership(quiz_client: TestClient) -> None:
    _, alice_headers = register(quiz_client)
    _, bob_headers = register(quiz_client)
    alice_course = create_course(quiz_client, alice_headers)
    bob_course = create_course(quiz_client, bob_headers)
    bob_document = asyncio.run(seed_document(bob_course))

    foreign_document = quiz_client.post(
        f"/courses/{alice_course}/quizzes",
        json={"document_ids": [str(bob_document)], "multiple_choice_count": 1},
        headers=alice_headers,
    )
    assert foreign_document.status_code == 404
    assert foreign_document.json()["code"] == "document_not_found"

    alice_document = asyncio.run(seed_document(alice_course))
    created = quiz_client.post(
        f"/courses/{alice_course}/quizzes",
        json={"document_ids": [str(alice_document)], "multiple_choice_count": 1},
        headers=alice_headers,
    )
    quiz_id = created.json()["id"]
    foreign_detail = quiz_client.get(f"/quizzes/{quiz_id}", headers=bob_headers)
    assert foreign_detail.status_code == 404
    assert foreign_detail.json()["code"] == "quiz_not_found"


def test_non_ready_document_is_rejected(quiz_client: TestClient) -> None:
    _, headers = register(quiz_client)
    course_id = create_course(quiz_client, headers)
    document_id = asyncio.run(seed_document(course_id, ready=False))
    response = quiz_client.post(
        f"/courses/{course_id}/quizzes",
        json={"document_ids": [str(document_id)], "multiple_choice_count": 1},
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["code"] == "document_not_ready"


def test_daily_quiz_quota_is_enforced_before_model_call(
    object_storage: FakeObjectStorage,
) -> None:
    chat = QuizChatClient()

    async def scheduler(_document_id: UUID) -> None:
        return None

    app = create_app(
        object_storage=object_storage,
        document_scheduler=scheduler,
        embedding_client=NoopEmbeddingClient(),
        chat_client=chat,
    )
    app.dependency_overrides[get_settings] = lambda: Settings(daily_quiz_quota=1)
    with TestClient(app) as client:
        _, headers = register(client)
        course_id = create_course(client, headers)
        document_id = asyncio.run(seed_document(course_id))
        endpoint = f"/courses/{course_id}/quizzes"
        body = {"document_ids": [str(document_id)], "multiple_choice_count": 1}
        first = client.post(endpoint, json=body, headers=headers)
        second = client.post(endpoint, json=body, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 429
    assert second.json()["code"] == "quiz_quota_exceeded"
    assert chat.calls == 1


def test_quiz_request_count_limits_use_stable_validation_error(
    quiz_client: TestClient,
) -> None:
    _, headers = register(quiz_client)
    course_id = create_course(quiz_client, headers)
    response = quiz_client.post(
        f"/courses/{course_id}/quizzes",
        json={
            "document_ids": [str(uuid4())],
            "multiple_choice_count": 10,
            "short_answer_count": 1,
        },
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_invalid_generation_does_not_persist_partial_quiz(
    object_storage: FakeObjectStorage,
) -> None:
    async def scheduler(_document_id: UUID) -> None:
        return None

    app = create_app(
        object_storage=object_storage,
        document_scheduler=scheduler,
        embedding_client=NoopEmbeddingClient(),
        chat_client=InvalidQuizChatClient(),
    )
    with TestClient(app) as client:
        _, headers = register(client)
        course_id = create_course(client, headers)
        document_id = asyncio.run(seed_document(course_id))
        response = client.post(
            f"/courses/{course_id}/quizzes",
            json={"document_ids": [str(document_id)], "multiple_choice_count": 1},
            headers=headers,
        )
        listed = client.get(f"/courses/{course_id}/quizzes", headers=headers)

    assert response.status_code == 502
    assert response.json()["code"] == "quiz_generation_invalid"
    assert listed.json() == []
