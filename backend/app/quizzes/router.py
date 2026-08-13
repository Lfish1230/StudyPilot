from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.interfaces import ChatClient
from app.auth.dependencies import CurrentUser
from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.quizzes.models import Question, Quiz
from app.quizzes.schemas import (
    QuizCreate,
    QuizDetailResponse,
    QuizQuestionResponse,
    QuizSummaryResponse,
)
from app.quizzes.service import create_quiz, get_owned_quiz, list_quizzes

router = APIRouter(tags=["quizzes"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_chat_client(request: Request) -> ChatClient:
    return cast(ChatClient, request.app.state.chat_client)


Chat = Annotated[ChatClient, Depends(get_chat_client)]


def _summary(quiz: Quiz) -> QuizSummaryResponse:
    return QuizSummaryResponse.model_validate(quiz)


def _question_response(question: Question) -> QuizQuestionResponse:
    return QuizQuestionResponse(
        id=question.id,
        type=str(question.type),
        position=question.position,
        prompt=question.prompt,
        options=question.options,
        knowledge_point=question.knowledge_point,
        difficulty=str(question.difficulty),
        source_document_id=question.source_document_id,
        source_document_name=question.source_document_name,
        source_page=question.source_page,
    )


@router.post(
    "/courses/{course_id}/quizzes",
    response_model=QuizDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_course_quiz(
    course_id: UUID,
    payload: QuizCreate,
    user: CurrentUser,
    session: DatabaseSession,
    chat: Chat,
    settings: Annotated[Settings, Depends(get_settings)],
) -> QuizDetailResponse:
    quiz = await create_quiz(session, user.id, course_id, payload, settings, chat)
    return QuizDetailResponse(
        **_summary(quiz).model_dump(),
        questions=[_question_response(question) for question in quiz.questions],
    )


@router.get("/courses/{course_id}/quizzes", response_model=list[QuizSummaryResponse])
async def list_course_quizzes(
    course_id: UUID, user: CurrentUser, session: DatabaseSession
) -> list[QuizSummaryResponse]:
    quizzes = await list_quizzes(session, user.id, course_id)
    return [_summary(quiz) for quiz in quizzes]


@router.get("/quizzes/{quiz_id}", response_model=QuizDetailResponse)
async def get_quiz(
    quiz_id: UUID, user: CurrentUser, session: DatabaseSession
) -> QuizDetailResponse:
    quiz = await get_owned_quiz(session, user.id, quiz_id)
    return QuizDetailResponse(
        **_summary(quiz).model_dump(),
        questions=[_question_response(question) for question in quiz.questions],
    )
