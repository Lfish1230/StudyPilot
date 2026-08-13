from collections.abc import Awaitable, Callable
from uuid import UUID

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.core.config import get_settings
from app.core.errors import (
    ApiError,
    api_error_handler,
    validation_error_handler,
)
from app.core.middleware import RequestIdMiddleware
from app.courses.router import router as courses_router
from app.documents.router import router as documents_router
from app.documents.storage import ObjectStorage, create_object_storage

DocumentScheduler = Callable[[UUID], Awaitable[None]]


async def schedule_document_processing(document_id: UUID) -> None:
    del document_id


def create_app(
    object_storage: ObjectStorage | None = None,
    document_scheduler: DocumentScheduler | None = None,
) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="StudyPilot API", version="0.1.0")
    app.state.object_storage = object_storage or create_object_storage(settings)
    app.state.document_scheduler = document_scheduler or schedule_document_processing

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

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
