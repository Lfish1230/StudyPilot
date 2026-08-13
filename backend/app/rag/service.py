import re
from dataclasses import dataclass
from datetime import UTC, datetime, time
from time import perf_counter
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.interfaces import ChatClient, EmbeddingClient
from app.ai.types import ChatUnavailableError, EmbeddingUnavailableError, TokenUsage
from app.core.config import Settings
from app.core.errors import ApiError, NotFoundError, ServiceUnavailableError
from app.courses.service import get_owned_course
from app.documents.model import Document, DocumentStatus
from app.rag.conversation_models import (
    Conversation,
    ConversationMessage,
    MessageCitation,
    MessageRole,
)
from app.rag.prompts import REFUSAL_TEXT, build_rag_messages
from app.rag.repository import RetrievedChunk, retrieve_chunks

_CITATION_PATTERN = re.compile(r"\[([Ss]\d+)\]")


@dataclass(frozen=True, slots=True)
class AnswerCitation:
    source_id: str
    document_id: UUID
    document_name: str
    page_number: int
    snippet: str
    distance: float


@dataclass(frozen=True, slots=True)
class AssistantAnswer:
    text: str
    refused: bool
    citations: list[AnswerCitation]
    model: str | None
    usage: TokenUsage


class RagService:
    def __init__(self, chat_client: ChatClient) -> None:
        self._chat_client = chat_client

    async def compose_answer(
        self, question: str, retrieved: list[RetrievedChunk]
    ) -> AssistantAnswer:
        question = question.strip()
        if not question:
            raise ApiError(422, "empty_question", "问题不能为空。")
        if not retrieved:
            return AssistantAnswer(
                text=REFUSAL_TEXT,
                refused=True,
                citations=[],
                model=None,
                usage=TokenUsage(0, 0),
            )

        try:
            result = await self._chat_client.complete(
                build_rag_messages(question, retrieved)
            )
        except ChatUnavailableError as exc:
            raise ServiceUnavailableError(
                "chat_unavailable", "问答服务暂时不可用，请稍后重试。"
            ) from exc

        source_by_id = {chunk.source_id.upper(): chunk for chunk in retrieved}
        cited_ids: list[str] = []

        def sanitize_citation(match: re.Match[str]) -> str:
            source_id = match.group(1).upper()
            if source_id not in source_by_id:
                return ""
            if source_id not in cited_ids:
                cited_ids.append(source_id)
            return f"[{source_id}]"

        text = _CITATION_PATTERN.sub(sanitize_citation, result.content).strip()
        refused = text == REFUSAL_TEXT
        if not refused and not cited_ids:
            raise ApiError(
                502,
                "answer_missing_citation",
                "模型回答缺少有效资料引用，请重试。",
            )

        citations = [
            AnswerCitation(
                source_id=source_id,
                document_id=source_by_id[source_id].document_id,
                document_name=source_by_id[source_id].document_name,
                page_number=source_by_id[source_id].page_number,
                snippet=source_by_id[source_id].content[:300],
                distance=source_by_id[source_id].distance,
            )
            for source_id in cited_ids
        ]
        return AssistantAnswer(
            text=text,
            refused=refused,
            citations=citations,
            model=result.model,
            usage=result.usage,
        )


async def get_owned_conversation(
    session: AsyncSession, user_id: UUID, conversation_id: UUID
) -> Conversation:
    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )
    if conversation is None:
        raise NotFoundError("conversation_not_found", "对话不存在。")
    return conversation


async def create_conversation(
    session: AsyncSession, user_id: UUID, course_id: UUID
) -> Conversation:
    await get_owned_course(session, user_id, course_id)
    conversation = Conversation(course_id=course_id, user_id=user_id)
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def list_conversations(
    session: AsyncSession, user_id: UUID, course_id: UUID
) -> list[Conversation]:
    await get_owned_course(session, user_id, course_id)
    return list(
        await session.scalars(
            select(Conversation)
            .where(
                Conversation.course_id == course_id,
                Conversation.user_id == user_id,
            )
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        )
    )


async def list_messages(
    session: AsyncSession, user_id: UUID, conversation_id: UUID
) -> list[ConversationMessage]:
    await get_owned_conversation(session, user_id, conversation_id)
    return list(
        await session.scalars(
            select(ConversationMessage)
            .options(selectinload(ConversationMessage.citations))
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at, ConversationMessage.id)
        )
    )


async def _enforce_question_quota(
    session: AsyncSession, user_id: UUID, settings: Settings
) -> None:
    start = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
    count = await session.scalar(
        select(func.count(ConversationMessage.id))
        .join(
            Conversation,
            Conversation.id == ConversationMessage.conversation_id,
        )
        .where(
            Conversation.user_id == user_id,
            ConversationMessage.role == MessageRole.USER,
            ConversationMessage.created_at >= start,
        )
    )
    if int(count or 0) >= settings.daily_question_quota:
        raise ApiError(
            429,
            "question_quota_exceeded",
            "今天的资料问答次数已用完，请明天再试。",
        )


async def answer_question(
    session: AsyncSession,
    user_id: UUID,
    conversation_id: UUID,
    question: str,
    settings: Settings,
    embedding_client: EmbeddingClient,
    rag_service: RagService,
) -> ConversationMessage:
    asked_at = datetime.now(UTC)
    conversation = await get_owned_conversation(session, user_id, conversation_id)
    ready_count = await session.scalar(
        select(func.count(Document.id)).where(
            Document.course_id == conversation.course_id,
            Document.status == DocumentStatus.READY,
        )
    )
    if int(ready_count or 0) == 0:
        raise ApiError(
            409,
            "document_not_ready",
            "请等待至少一份课程文档处理完成。",
        )
    await _enforce_question_quota(session, user_id, settings)
    # Release the read transaction before waiting on an external provider call.
    await session.commit()

    started_at = perf_counter()
    try:
        query_vectors = await embedding_client.embed([question])
    except EmbeddingUnavailableError as exc:
        raise ServiceUnavailableError(
            "embedding_unavailable", "资料检索服务暂时不可用，请稍后重试。"
        ) from exc
    if len(query_vectors) != 1:
        raise ServiceUnavailableError(
            "embedding_unavailable", "资料检索服务暂时不可用，请稍后重试。"
        )
    retrieved = await retrieve_chunks(session, conversation.course_id, query_vectors[0])
    # Retrieved chunks are detached dataclasses, so the database transaction can
    # be released while the chat provider generates the answer.
    await session.commit()
    answer = await rag_service.compose_answer(question, retrieved)
    latency_ms = round((perf_counter() - started_at) * 1000)

    user_message = ConversationMessage(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=question,
        created_at=asked_at,
    )
    assistant_message = ConversationMessage(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=answer.text,
        refused=answer.refused,
        model=answer.model,
        input_tokens=answer.usage.input_tokens,
        output_tokens=answer.usage.output_tokens,
        latency_ms=latency_ms,
        created_at=datetime.now(UTC),
    )
    assistant_message.citations = [
        MessageCitation(
            source_id=citation.source_id,
            document_id=citation.document_id,
            document_name=citation.document_name,
            page_number=citation.page_number,
            snippet=citation.snippet,
            distance=citation.distance,
        )
        for citation in answer.citations
    ]
    session.add_all([user_message, assistant_message])
    conversation.updated_at = datetime.now(UTC)
    await session.commit()
    return assistant_message
