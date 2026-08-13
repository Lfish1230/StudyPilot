from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.interfaces import ChatClient, EmbeddingClient
from app.auth.dependencies import CurrentUser
from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.rag.conversation_models import ConversationMessage
from app.rag.schemas import (
    CitationResponse,
    ConversationResponse,
    MessageResponse,
    QuestionCreate,
)
from app.rag.service import (
    RagService,
    answer_question,
    create_conversation,
    list_conversations,
    list_messages,
)

router = APIRouter(tags=["conversations"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_embedding_client(request: Request) -> EmbeddingClient:
    return cast(EmbeddingClient, request.app.state.embedding_client)


def get_chat_client(request: Request) -> ChatClient:
    return cast(ChatClient, request.app.state.chat_client)


Embeddings = Annotated[EmbeddingClient, Depends(get_embedding_client)]
Chat = Annotated[ChatClient, Depends(get_chat_client)]


def _message_response(message: ConversationMessage) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        role=str(message.role),
        content=message.content,
        refused=message.refused,
        model=message.model,
        input_tokens=message.input_tokens,
        output_tokens=message.output_tokens,
        latency_ms=message.latency_ms,
        citations=[CitationResponse.model_validate(item) for item in message.citations],
        created_at=message.created_at,
    )


@router.post(
    "/courses/{course_id}/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_course_conversation(
    course_id: UUID, user: CurrentUser, session: DatabaseSession
) -> ConversationResponse:
    conversation = await create_conversation(session, user.id, course_id)
    return ConversationResponse.model_validate(conversation)


@router.get(
    "/courses/{course_id}/conversations",
    response_model=list[ConversationResponse],
)
async def list_course_conversations(
    course_id: UUID, user: CurrentUser, session: DatabaseSession
) -> list[ConversationResponse]:
    conversations = await list_conversations(session, user.id, course_id)
    return [
        ConversationResponse.model_validate(conversation)
        for conversation in conversations
    ]


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
async def get_conversation_messages(
    conversation_id: UUID, user: CurrentUser, session: DatabaseSession
) -> list[MessageResponse]:
    messages = await list_messages(session, user.id, conversation_id)
    return [_message_response(message) for message in messages]


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    conversation_id: UUID,
    payload: QuestionCreate,
    user: CurrentUser,
    session: DatabaseSession,
    embeddings: Embeddings,
    chat: Chat,
    settings: Annotated[Settings, Depends(get_settings)],
) -> MessageResponse:
    message = await answer_question(
        session,
        user.id,
        conversation_id,
        payload.question,
        settings,
        embeddings,
        RagService(chat),
    )
    return _message_response(message)
