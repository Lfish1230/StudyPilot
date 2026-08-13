import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.documents.model import Document, DocumentStatus
from app.quizzes.attempt_models import AttemptAnswer, QuizAttempt
from app.quizzes.models import Question, QuestionDifficulty, QuestionType, Quiz
from tests.conftest import CreatedUser


def register(client: TestClient) -> tuple[CreatedUser, dict[str, str]]:
    password = "correct-horse-42"
    email = f"analytics-{uuid4()}@example.com"
    response = client.post(
        "/auth/register", json={"email": email, "password": password}
    )
    user = CreatedUser(response.json()["id"], email, password)
    login = client.post("/auth/login", json={"email": email, "password": password})
    return user, {"Authorization": f"Bearer {login.json()['access_token']}"}


def create_course(client: TestClient, headers: dict[str, str]) -> UUID:
    response = client.post("/courses", json={"name": "数据结构"}, headers=headers)
    return UUID(response.json()["id"])


async def seed_attempts(course_id: UUID, user_id: str) -> None:
    document_id = uuid4()
    quiz_one = Quiz(
        course_id=course_id,
        user_id=UUID(user_id),
        title="测验一",
        question_count=2,
        model="fixture",
        input_tokens=0,
        output_tokens=0,
    )
    quiz_one.questions = [
        Question(
            type=QuestionType.MULTIPLE_CHOICE,
            position=1,
            prompt="栈题",
            options=["A", "B", "C", "D"],
            standard_answer="A",
            rubric_points=None,
            explanation="栈解析",
            knowledge_point="栈",
            difficulty=QuestionDifficulty.EASY,
            source_document_id=document_id,
            source_document_name="ds.pdf",
            source_page=3,
        ),
        Question(
            type=QuestionType.MULTIPLE_CHOICE,
            position=2,
            prompt="队列题",
            options=["A", "B", "C", "D"],
            standard_answer="B",
            rubric_points=None,
            explanation="队列解析",
            knowledge_point="队列",
            difficulty=QuestionDifficulty.EASY,
            source_document_id=document_id,
            source_document_name="ds.pdf",
            source_page=4,
        ),
    ]
    quiz_two = Quiz(
        course_id=course_id,
        user_id=UUID(user_id),
        title="测验二",
        question_count=1,
        model="fixture",
        input_tokens=0,
        output_tokens=0,
    )
    quiz_two.questions = [
        Question(
            type=QuestionType.SHORT_ANSWER,
            position=1,
            prompt="再答栈",
            options=None,
            standard_answer="后进先出",
            rubric_points=["后进先出"],
            explanation="栈解析二",
            knowledge_point="栈",
            difficulty=QuestionDifficulty.MEDIUM,
            source_document_id=document_id,
            source_document_name="ds.pdf",
            source_page=5,
        )
    ]
    async with SessionLocal() as session:
        session.add(
            Document(
                id=document_id,
                course_id=course_id,
                original_name="ds.pdf",
                object_key=f"analytics/{document_id}.pdf",
                size_bytes=100,
                page_count=5,
                status=DocumentStatus.READY,
            )
        )
        session.add_all([quiz_one, quiz_two])
        await session.flush()
        attempt_one = QuizAttempt(
            quiz_id=quiz_one.id,
            user_id=UUID(user_id),
            total_score=0,
            max_score=20,
            submitted_at=datetime.now(UTC) - timedelta(hours=1),
            answers=[
                AttemptAnswer(
                    question_id=quiz_one.questions[0].id,
                    user_answer="B",
                    score=0,
                    is_correct=False,
                    feedback="错误",
                    missing_points=["后进先出"],
                ),
                AttemptAnswer(
                    question_id=quiz_one.questions[1].id,
                    user_answer="B",
                    score=0,
                    is_correct=False,
                    feedback="错误",
                    missing_points=["先进先出"],
                ),
            ],
        )
        attempt_two = QuizAttempt(
            quiz_id=quiz_two.id,
            user_id=UUID(user_id),
            total_score=10,
            max_score=10,
            submitted_at=datetime.now(UTC),
            answers=[
                AttemptAnswer(
                    question_id=quiz_two.questions[0].id,
                    user_answer="先进先出",
                    score=10,
                    is_correct=True,
                    feedback="正确",
                    missing_points=[],
                )
            ],
        )
        session.add_all([attempt_one, attempt_two])
        await session.commit()


def test_mistakes_and_course_analytics_are_owner_scoped(client: TestClient) -> None:
    user, headers = register(client)
    _, foreign_headers = register(client)
    course_id = create_course(client, headers)
    asyncio.run(seed_attempts(course_id, user.id))

    mistakes = client.get(f"/courses/{course_id}/mistakes", headers=headers)
    assert mistakes.status_code == 200
    assert [item["knowledge_point"] for item in mistakes.json()] == ["栈", "队列"]
    assert all(item["score"] < 6 for item in mistakes.json())
    assert mistakes.json()[0]["standard_answer"] == "A"
    assert mistakes.json()[0]["source_document_name"] == "ds.pdf"

    analytics = client.get(f"/courses/{course_id}/analytics", headers=headers)
    assert analytics.status_code == 200
    payload = analytics.json()
    assert payload["total_questions"] == 3
    assert payload["total_attempts"] == 2
    assert payload["average_percent_score"] == 50.0
    assert payload["weak_topics"] == [
        {
            "knowledge_point": "队列",
            "answered_count": 1,
            "wrong_count": 1,
            "weak_score": 1.0,
        },
        {
            "knowledge_point": "栈",
            "answered_count": 2,
            "wrong_count": 1,
            "weak_score": 0.5,
        },
    ]
    assert [item["quiz_title"] for item in payload["recent_attempts"]] == [
        "测验二",
        "测验一",
    ]

    foreign_mistakes = client.get(
        f"/courses/{course_id}/mistakes", headers=foreign_headers
    )
    assert foreign_mistakes.status_code == 404
    assert (
        client.get(
            f"/courses/{course_id}/analytics", headers=foreign_headers
        ).status_code
        == 404
    )


def test_empty_analytics_never_returns_nan(client: TestClient) -> None:
    _, headers = register(client)
    course_id = create_course(client, headers)
    response = client.get(f"/courses/{course_id}/analytics", headers=headers)
    assert response.status_code == 200
    assert response.json() == {
        "total_questions": 0,
        "total_attempts": 0,
        "average_percent_score": 0.0,
        "weak_topics": [],
        "recent_attempts": [],
    }
