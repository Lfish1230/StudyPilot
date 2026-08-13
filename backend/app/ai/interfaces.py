from typing import Protocol
from uuid import UUID

from app.documents.chunker import TextChunk


class EmbeddingClient(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class ChunkSink(Protocol):
    async def replace(
        self,
        document_id: UUID,
        course_id: UUID,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
    ) -> None: ...
