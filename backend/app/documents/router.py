from collections.abc import Awaitable, Callable
from typing import Annotated, cast
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.documents.schemas import DocumentResponse
from app.documents.service import (
    create_document,
    delete_document,
    get_owned_document,
    list_course_documents,
    prepare_document_retry,
)
from app.documents.storage import ObjectStorage

DocumentScheduler = Callable[[UUID], Awaitable[None]]
router = APIRouter(tags=["documents"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_storage(request: Request) -> ObjectStorage:
    return cast(ObjectStorage, request.app.state.object_storage)


def get_scheduler(request: Request) -> DocumentScheduler:
    return cast(DocumentScheduler, request.app.state.document_scheduler)


Storage = Annotated[ObjectStorage, Depends(get_storage)]
Scheduler = Annotated[DocumentScheduler, Depends(get_scheduler)]


@router.post(
    "/courses/{course_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    course_id: UUID,
    user: CurrentUser,
    session: DatabaseSession,
    storage: Storage,
    scheduler: Scheduler,
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentResponse:
    data = await file.read(settings.max_pdf_bytes + 1)
    document = await create_document(
        session,
        storage,
        settings,
        user.id,
        course_id,
        file.filename or "document.pdf",
        data,
        file.content_type,
    )
    background_tasks.add_task(scheduler, document.id)
    return DocumentResponse.model_validate(document)


@router.get("/courses/{course_id}/documents", response_model=list[DocumentResponse])
async def list_documents(
    course_id: UUID, user: CurrentUser, session: DatabaseSession
) -> list[DocumentResponse]:
    documents = await list_course_documents(session, user.id, course_id)
    return [DocumentResponse.model_validate(document) for document in documents]


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID, user: CurrentUser, session: DatabaseSession
) -> DocumentResponse:
    document = await get_owned_document(session, user.id, document_id)
    return DocumentResponse.model_validate(document)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_document(
    document_id: UUID,
    user: CurrentUser,
    session: DatabaseSession,
    storage: Storage,
) -> Response:
    document = await get_owned_document(session, user.id, document_id)
    await delete_document(session, storage, document)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/documents/{document_id}/retry", response_model=DocumentResponse)
async def retry_document(
    document_id: UUID,
    user: CurrentUser,
    session: DatabaseSession,
    scheduler: Scheduler,
    background_tasks: BackgroundTasks,
) -> DocumentResponse:
    document = await get_owned_document(session, user.id, document_id)
    document = await prepare_document_retry(session, document)
    background_tasks.add_task(scheduler, document.id)
    return DocumentResponse.model_validate(document)
