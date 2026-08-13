from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.documents.chunker import TextChunk
from app.documents.model import Document, DocumentStatus
from app.rag.model import DocumentChunk


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    source_id: str
    document_id: UUID
    document_name: str
    page_number: int
    content: str
    token_count: int
    distance: float


class PgVectorChunkSink:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        batch_size: int = 20,
    ) -> None:
        self._session_factory = session_factory
        self._batch_size = batch_size

    async def replace(
        self,
        document_id: UUID,
        course_id: UUID,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunk and embedding counts must match")
        async with self._session_factory() as session:
            await session.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
            )
            for start in range(0, len(chunks), self._batch_size):
                batch_chunks = chunks[start : start + self._batch_size]
                batch_embeddings = embeddings[start : start + self._batch_size]
                session.add_all(
                    [
                        DocumentChunk(
                            document_id=document_id,
                            course_id=course_id,
                            page_number=chunk.page_number,
                            content=chunk.content,
                            token_count=chunk.token_count,
                            embedding=embedding,
                        )
                        for chunk, embedding in zip(
                            batch_chunks, batch_embeddings, strict=True
                        )
                    ]
                )
                await session.flush()
            await session.commit()


async def retrieve_chunks(
    session: AsyncSession,
    course_id: UUID,
    query_vector: list[float],
    limit: int = 5,
    max_distance: float = 0.40,
) -> list[RetrievedChunk]:
    distance = DocumentChunk.embedding.cosine_distance(query_vector).label("distance")
    rows = (
        await session.execute(
            select(DocumentChunk, Document.original_name, distance)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.course_id == course_id,
                Document.status == DocumentStatus.READY,
                distance <= max_distance,
            )
            .order_by(distance)
            .limit(min(limit, 5))
        )
    ).all()
    return [
        RetrievedChunk(
            source_id=f"S{index}",
            document_id=chunk.document_id,
            document_name=document_name,
            page_number=chunk.page_number,
            content=chunk.content,
            token_count=chunk.token_count,
            distance=float(row_distance),
        )
        for index, (chunk, document_name, row_distance) in enumerate(rows, start=1)
    ]


async def get_document_context(
    session: AsyncSession,
    document_ids: list[UUID],
    token_budget: int,
) -> list[DocumentChunk]:
    if not document_ids or token_budget <= 0:
        return []
    chunks = list(
        await session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id.in_(document_ids))
            .order_by(
                DocumentChunk.document_id,
                DocumentChunk.page_number,
                DocumentChunk.id,
            )
        )
    )
    selected: list[DocumentChunk] = []
    used_tokens = 0
    for chunk in chunks:
        if used_tokens + chunk.token_count > token_budget:
            break
        selected.append(chunk)
        used_tokens += chunk.token_count
    return selected
