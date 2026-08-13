from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.schemas import (
    CourseAnalyticsResponse,
    MistakeResponse,
    RecentAttemptResponse,
    WeakTopicResponse,
)
from app.courses.service import get_owned_course
from app.quizzes.attempt_models import AttemptAnswer, QuizAttempt
from app.quizzes.models import Question, Quiz


async def list_mistakes(
    session: AsyncSession, user_id: UUID, course_id: UUID
) -> list[MistakeResponse]:
    await get_owned_course(session, user_id, course_id)
    rows = (
        await session.execute(
            select(AttemptAnswer, QuizAttempt, Question, Quiz)
            .join(QuizAttempt, QuizAttempt.id == AttemptAnswer.attempt_id)
            .join(Question, Question.id == AttemptAnswer.question_id)
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .where(
                Quiz.course_id == course_id,
                QuizAttempt.user_id == user_id,
                AttemptAnswer.score < 6,
            )
            .order_by(QuizAttempt.submitted_at.desc(), Question.position)
        )
    ).all()
    return [
        MistakeResponse(
            attempt_id=attempt.id,
            quiz_id=quiz.id,
            quiz_title=quiz.title,
            question_id=question.id,
            type=str(question.type),
            prompt=question.prompt,
            user_answer=answer.user_answer,
            standard_answer=question.standard_answer,
            explanation=question.explanation,
            score=answer.score,
            feedback=answer.feedback,
            missing_points=answer.missing_points,
            knowledge_point=question.knowledge_point,
            source_document_id=question.source_document_id,
            source_document_name=question.source_document_name,
            source_page=question.source_page,
            submitted_at=attempt.submitted_at,
        )
        for answer, attempt, question, quiz in rows
    ]


async def get_course_analytics(
    session: AsyncSession, user_id: UUID, course_id: UUID
) -> CourseAnalyticsResponse:
    await get_owned_course(session, user_id, course_id)
    base_conditions = (Quiz.course_id == course_id, QuizAttempt.user_id == user_id)
    attempt_totals = (
        await session.execute(
            select(
                func.count(QuizAttempt.id),
                func.coalesce(
                    func.avg(
                        QuizAttempt.total_score
                        * 100.0
                        / func.nullif(QuizAttempt.max_score, 0)
                    ),
                    0.0,
                ),
            )
            .select_from(QuizAttempt)
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .where(*base_conditions)
        )
    ).one()
    total_questions = await session.scalar(
        select(func.count(AttemptAnswer.id))
        .join(QuizAttempt, QuizAttempt.id == AttemptAnswer.attempt_id)
        .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .where(*base_conditions)
    )

    answered_count = func.count(AttemptAnswer.id)
    wrong_count = func.sum(case((AttemptAnswer.score < 6, 1), else_=0))
    topic_rows = (
        await session.execute(
            select(Question.knowledge_point, answered_count, wrong_count)
            .select_from(AttemptAnswer)
            .join(QuizAttempt, QuizAttempt.id == AttemptAnswer.attempt_id)
            .join(Question, Question.id == AttemptAnswer.question_id)
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .where(*base_conditions)
            .group_by(Question.knowledge_point)
            .order_by(
                (wrong_count * 1.0 / answered_count).desc(),
                answered_count.desc(),
                Question.knowledge_point,
            )
        )
    ).all()
    weak_topics = [
        WeakTopicResponse(
            knowledge_point=knowledge_point,
            answered_count=int(answered),
            wrong_count=int(wrong),
            weak_score=float(wrong) / int(answered),
        )
        for knowledge_point, answered, wrong in topic_rows
    ]

    recent_rows = (
        await session.execute(
            select(QuizAttempt, Quiz.title)
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .where(*base_conditions)
            .order_by(QuizAttempt.submitted_at.desc(), QuizAttempt.id.desc())
            .limit(10)
        )
    ).all()
    recent_attempts = [
        RecentAttemptResponse(
            attempt_id=attempt.id,
            quiz_id=attempt.quiz_id,
            quiz_title=title,
            total_score=attempt.total_score,
            max_score=attempt.max_score,
            percentage=(
                attempt.total_score / attempt.max_score * 100
                if attempt.max_score
                else 0.0
            ),
            submitted_at=attempt.submitted_at,
        )
        for attempt, title in recent_rows
    ]
    return CourseAnalyticsResponse(
        total_questions=int(total_questions or 0),
        total_attempts=int(attempt_totals[0]),
        average_percent_score=float(attempt_totals[1]),
        weak_topics=weak_topics,
        recent_attempts=recent_attempts,
    )
