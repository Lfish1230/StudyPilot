import asyncio
import json
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.ai.types import ChatMessage, ChatResult, TokenUsage
from app.core.database import SessionLocal
from app.documents.model import Document, DocumentStatus
from app.documents.storage import FakeObjectStorage
from app.main import create_app
from app.quizzes.attempt_models import QuizAttempt
from app.quizzes.models import Question, QuestionDifficulty, QuestionType, Quiz
from tests.conftest import CreatedUser


class GradingChatClient:
    def __init__(self, *, invalid: bool = False) -> None:
        self.invalid = invalid
        self.calls = 0

    async def complete(
        self,
        messages: list[ChatMessage],
        response_format: dict[str, object] | None = None,
    ) -> ChatResult:
        del messages, response_format
        self.calls += 1
        content = (
            "invalid"
            if self.invalid
            else json.dumps(
                {"score": 7, "feedback": "基本正确。", "missing_points": ["接收能力"]},
                ensure_ascii=False,
            )
        )
        return ChatResult(content, "fake-grader", TokenUsage(10, 5))


@pytest.fixture
def submission_client(object_storage: FakeObjectStorage) -> Iterator[TestClient]:
    app = create_app(object_storage=object_storage, chat_client=GradingChatClient())
    with TestClient(app) as client:
        yield client


def register(client: TestClient) -> tuple[CreatedUser, dict[str, str]]:
    password = "correct-horse-42"
    email = f"submit-{uuid4()}@example.com"
    response = client.post(
        "/auth/register", json={"email": email, "password": password}
    )
    user = CreatedUser(response.json()["id"], email, password)
    login = client.post("/auth/login", json={"email": email, "password": password})
    return user, {"Authorization": f"Bearer {login.json()['access_token']}"}


def create_course(client: TestClient, headers: dict[str, str]) -> UUID:
    response = client.post("/courses", json={"name": "网络"}, headers=headers)
    return UUID(response.json()["id"])


async def seed_quiz(course_id: UUID, user_id: str) -> tuple[UUID, list[UUID]]:
    document_id = uuid4()
    quiz = Quiz(
        course_id=course_id,
        user_id=UUID(user_id),
        title="网络测验",
        question_count=2,
        model="fixture",
        input_tokens=0,
        output_tokens=0,
    )
    quiz.questions = [
        Question(
            type=QuestionType.MULTIPLE_CHOICE,
            position=1,
            prompt="正确选项？",
            options=["A", "B", "C", "D"],
            standard_answer="B",
            rubric_points=None,
            explanation="B 是正确选项。",
            knowledge_point="选择知识点",
            difficulty=QuestionDifficulty.EASY,
            source_document_id=document_id,
            source_document_name="network.pdf",
            source_page=1,
        ),
        Question(
            type=QuestionType.SHORT_ANSWER,
            position=2,
            prompt="简述握手作用。",
            options=None,
            standard_answer="确认双方收发能力。",
            rubric_points=["发送能力", "接收能力"],
            explanation="握手确认通信能力。",
            knowledge_point="TCP 握手",
            difficulty=QuestionDifficulty.MEDIUM,
            source_document_id=document_id,
            source_document_name="network.pdf",
            source_page=2,
        ),
    ]
    async with SessionLocal() as session:
        session.add(
            Document(
                id=document_id,
                course_id=course_id,
                original_name="network.pdf",
                object_key=f"attempt/{document_id}.pdf",
                size_bytes=100,
                page_count=2,
                status=DocumentStatus.READY,
            )
        )
        session.add(quiz)
        await session.commit()
        return quiz.id, [question.id for question in quiz.questions]


def submission_body(question_ids: list[UUID]) -> dict[str, object]:
    return {
        "answers": [
            {"question_id": str(question_ids[0]), "answer": "A"},
            {"question_id": str(question_ids[1]), "answer": "确认发送能力"},
        ]
    }


def test_submit_returns_full_feedback_and_prevents_resubmission(
    submission_client: TestClient,
) -> None:
    user, headers = register(submission_client)
    course_id = create_course(submission_client, headers)
    quiz_id, question_ids = asyncio.run(seed_quiz(course_id, user.id))
    endpoint = f"/quizzes/{quiz_id}/submit"

    response = submission_client.post(
        endpoint, json=submission_body(question_ids), headers=headers
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_score"] == 7
    assert payload["max_score"] == 20
    assert payload["percentage"] == 35.0
    assert payload["answers"][0]["standard_answer"] == "B"
    assert payload["answers"][0]["score"] == 0
    assert payload["answers"][1]["score"] == 7
    assert payload["answers"][1]["source_page"] == 2

    repeated = submission_client.post(
        endpoint, json=submission_body(question_ids), headers=headers
    )
    assert repeated.status_code == 409
    assert repeated.json()["code"] == "quiz_already_submitted"


def test_submission_requires_every_question_exactly_once(
    submission_client: TestClient,
) -> None:
    user, headers = register(submission_client)
    course_id = create_course(submission_client, headers)
    quiz_id, question_ids = asyncio.run(seed_quiz(course_id, user.id))
    endpoint = f"/quizzes/{quiz_id}/submit"

    missing = submission_client.post(
        endpoint,
        json={"answers": [{"question_id": str(question_ids[0]), "answer": "B"}]},
        headers=headers,
    )
    duplicate = submission_client.post(
        endpoint,
        json={
            "answers": [
                {"question_id": str(question_ids[0]), "answer": "B"},
                {"question_id": str(question_ids[0]), "answer": "B"},
            ]
        },
        headers=headers,
    )
    assert missing.status_code == 422
    assert missing.json()["code"] == "answer_set_invalid"
    assert duplicate.status_code == 422
    assert duplicate.json()["code"] == "validation_error"


def test_foreign_quiz_is_hidden(submission_client: TestClient) -> None:
    owner, owner_headers = register(submission_client)
    _, foreign_headers = register(submission_client)
    course_id = create_course(submission_client, owner_headers)
    quiz_id, question_ids = asyncio.run(seed_quiz(course_id, owner.id))
    response = submission_client.post(
        f"/quizzes/{quiz_id}/submit",
        json=submission_body(question_ids),
        headers=foreign_headers,
    )
    assert response.status_code == 404
    assert response.json()["code"] == "quiz_not_found"


def test_grading_failure_rolls_back_entire_attempt(
    object_storage: FakeObjectStorage,
) -> None:
    app = create_app(
        object_storage=object_storage,
        chat_client=GradingChatClient(invalid=True),
    )
    with TestClient(app) as client:
        user, headers = register(client)
        course_id = create_course(client, headers)
        quiz_id, question_ids = asyncio.run(seed_quiz(course_id, user.id))
        response = client.post(
            f"/quizzes/{quiz_id}/submit",
            json=submission_body(question_ids),
            headers=headers,
        )

    async def attempt_count() -> int:
        async with SessionLocal() as session:
            value = await session.scalar(select(func.count(QuizAttempt.id)))
            return int(value or 0)

    assert response.status_code == 503
    assert response.json()["code"] == "grading_unavailable"
    assert asyncio.run(attempt_count()) == 0
