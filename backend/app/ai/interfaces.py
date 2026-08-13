from typing import Protocol
from uuid import UUID

from app.ai.types import ChatMessage, ChatResult
from app.documents.chunker import TextChunk


class EmbeddingClient(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class ChatClient(Protocol):
    async def complete(
        self,
        messages: list[ChatMessage],
        response_format: dict[str, object] | None = None,
    ) -> ChatResult: ...


class ChunkSink(Protocol):
    async def replace(
        self,
        document_id: UUID,
        course_id: UUID,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
    ) -> None: ...
