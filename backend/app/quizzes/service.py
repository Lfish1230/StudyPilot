from dataclasses import dataclass
from datetime import UTC, datetime, time
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.interfaces import ChatClient
from app.core.config import Settings
from app.core.errors import ApiError, NotFoundError
from app.courses.service import get_owned_course
from app.documents.model import Document, DocumentStatus
from app.quizzes.attempt_models import AttemptAnswer, QuizAttempt
from app.quizzes.generator import generate_quiz
from app.quizzes.grading import GradeResult, grade_multiple_choice, grade_short_answer
from app.quizzes.models import Question, QuestionDifficulty, QuestionType, Quiz
from app.quizzes.schemas import QuizCreate, QuizSubmission
from app.rag.repository import get_document_context


async def _enforce_quiz_quota(
    session: AsyncSession, user_id: UUID, settings: Settings
) -> None:
    start = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
    count = await session.scalar(
        select(func.count(Quiz.id)).where(
            Quiz.user_id == user_id,
            Quiz.created_at >= start,
        )
    )
    if int(count or 0) >= settings.daily_quiz_quota:
        raise ApiError(
            429,
            "quiz_quota_exceeded",
            "今天的测验生成次数已用完，请明天再试。",
        )


async def _get_ready_documents(
    session: AsyncSession,
    user_id: UUID,
    course_id: UUID,
    document_ids: list[UUID],
) -> list[Document]:
    await get_owned_course(session, user_id, course_id)
    documents = list(
        await session.scalars(
            select(Document).where(
                Document.course_id == course_id,
                Document.id.in_(document_ids),
            )
        )
    )
    if len(documents) != len(document_ids):
        raise NotFoundError("document_not_found", "文档不存在。")
    if any(document.status != DocumentStatus.READY for document in documents):
        raise ApiError(409, "document_not_ready", "所选文档尚未处理完成。")
    return documents


async def create_quiz(
    session: AsyncSession,
    user_id: UUID,
    course_id: UUID,
    payload: QuizCreate,
    settings: Settings,
    chat_client: ChatClient,
) -> Quiz:
    documents = await _get_ready_documents(
        session, user_id, course_id, payload.document_ids
    )
    await _enforce_quiz_quota(session, user_id, settings)
    chunks = await get_document_context(
        session, payload.document_ids, token_budget=7000
    )
    if not chunks:
        raise ApiError(409, "document_has_no_content", "所选文档没有可用的文本内容。")
    document_names = {document.id: document.original_name for document in documents}
    await session.commit()

    generated = await generate_quiz(
        chat_client,
        chunks,
        payload.multiple_choice_count,
        payload.short_answer_count,
    )
    quiz = Quiz(
        course_id=course_id,
        user_id=user_id,
        title=generated.quiz.title,
        question_count=len(generated.quiz.questions),
        model=generated.model,
        input_tokens=generated.usage.input_tokens,
        output_tokens=generated.usage.output_tokens,
    )
    quiz.questions = [
        Question(
            position=position,
            type=QuestionType(question.type),
            prompt=question.prompt,
            options=(question.options if question.type == "multiple_choice" else None),
            standard_answer=question.standard_answer,
            rubric_points=(
                question.rubric_points if question.type == "short_answer" else None
            ),
            explanation=question.explanation,
            knowledge_point=question.knowledge_point,
            difficulty=QuestionDifficulty(question.difficulty),
            source_document_id=question.source_document_id,
            source_document_name=document_names[question.source_document_id],
            source_page=question.source_page,
        )
        for position, question in enumerate(generated.quiz.questions, start=1)
    ]
    session.add(quiz)
    await session.commit()
    await session.refresh(quiz)
    return quiz


async def list_quizzes(
    session: AsyncSession, user_id: UUID, course_id: UUID
) -> list[Quiz]:
    await get_owned_course(session, user_id, course_id)
    return list(
        await session.scalars(
            select(Quiz)
            .where(Quiz.course_id == course_id, Quiz.user_id == user_id)
            .order_by(Quiz.created_at.desc(), Quiz.id.desc())
        )
    )


async def get_owned_quiz(session: AsyncSession, user_id: UUID, quiz_id: UUID) -> Quiz:
    quiz = await session.scalar(
        select(Quiz)
        .options(selectinload(Quiz.questions))
        .where(Quiz.id == quiz_id, Quiz.user_id == user_id)
    )
    if quiz is None:
        raise NotFoundError("quiz_not_found", "测验不存在。")
    return quiz


@dataclass(frozen=True, slots=True)
class SubmissionResult:
    attempt: QuizAttempt
    questions: dict[UUID, Question]


async def submit_quiz(
    session: AsyncSession,
    user_id: UUID,
    quiz_id: UUID,
    payload: QuizSubmission,
    chat_client: ChatClient,
) -> SubmissionResult:
    quiz = await get_owned_quiz(session, user_id, quiz_id)
    existing_attempt = await session.scalar(
        select(QuizAttempt.id).where(
            QuizAttempt.quiz_id == quiz_id,
            QuizAttempt.user_id == user_id,
        )
    )
    if existing_attempt is not None:
        raise ApiError(409, "quiz_already_submitted", "该测验已经提交过。")

    questions = {question.id: question for question in quiz.questions}
    submitted = {answer.question_id: answer.answer for answer in payload.answers}
    if submitted.keys() != questions.keys():
        raise ApiError(
            422,
            "answer_set_invalid",
            "必须为测验中的每一道题提交且只提交一个答案。",
        )
    await session.commit()

    graded_answers: list[AttemptAnswer] = []
    total_score = 0
    for question in quiz.questions:
        user_answer = submitted[question.id]
        grade: GradeResult
        if question.type == QuestionType.MULTIPLE_CHOICE:
            grade = grade_multiple_choice(user_answer, question.standard_answer)
        else:
            grade = await grade_short_answer(
                chat_client,
                question.prompt,
                user_answer,
                question.standard_answer,
                question.rubric_points or [],
            )
        total_score += grade.score
        graded_answers.append(
            AttemptAnswer(
                question_id=question.id,
                user_answer=user_answer,
                score=grade.score,
                is_correct=grade.score >= 6,
                feedback=grade.feedback,
                missing_points=grade.missing_points,
            )
        )

    attempt = QuizAttempt(
        quiz_id=quiz.id,
        user_id=user_id,
        total_score=total_score,
        max_score=len(quiz.questions) * 10,
        answers=graded_answers,
    )
    session.add(attempt)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(409, "quiz_already_submitted", "该测验已经提交过。") from exc
    await session.refresh(attempt)
    return SubmissionResult(attempt, questions)
