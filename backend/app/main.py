from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.ai.interfaces import ChatClient, ChunkSink, EmbeddingClient
from app.ai.qwen import QwenChatClient, QwenEmbeddingClient
from app.auth.router import router as auth_router
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.errors import (
    ApiError,
    api_error_handler,
    validation_error_handler,
)
from app.core.middleware import RequestIdMiddleware
from app.courses.router import router as courses_router
from app.documents.jobs import recover_stale_document_jobs
from app.documents.processor import process_document
from app.documents.router import router as documents_router
from app.documents.storage import ObjectStorage, create_object_storage
from app.quizzes.router import router as quizzes_router
from app.rag.repository import PgVectorChunkSink
from app.rag.router import router as rag_router

DocumentScheduler = Callable[[UUID], Awaitable[None]]


def create_app(
    object_storage: ObjectStorage | None = None,
    document_scheduler: DocumentScheduler | None = None,
    embedding_client: EmbeddingClient | None = None,
    chunk_sink: ChunkSink | None = None,
    chat_client: ChatClient | None = None,
) -> FastAPI:
    settings = get_settings()
    storage = object_storage or create_object_storage(settings)
    embeddings = embedding_client or QwenEmbeddingClient.from_settings(settings)
    sink = chunk_sink or PgVectorChunkSink(SessionLocal)
    chat = chat_client or QwenChatClient.from_settings(settings)

    async def production_scheduler(document_id: UUID) -> None:
        await process_document(
            document_id,
            SessionLocal,
            storage,
            embeddings,
            sink,
            max_pages=settings.max_pdf_pages,
        )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        async with SessionLocal() as session:
            await recover_stale_document_jobs(
                session, cutoff_minutes=settings.document_job_timeout_minutes
            )
        yield

    app = FastAPI(title="StudyPilot API", version="0.1.0", lifespan=lifespan)
    app.state.object_storage = storage
    app.state.document_scheduler = document_scheduler or production_scheduler
    app.state.embedding_client = embeddings
    app.state.chat_client = chat

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(
        RequestValidationError,
        validation_error_handler,  # type: ignore[arg-type]
    )
    app.include_router(auth_router)
    app.include_router(courses_router)
    app.include_router(documents_router)
    app.include_router(rag_router)
    app.include_router(quizzes_router)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
