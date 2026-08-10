from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.database import get_db_session
from app.courses.schemas import CourseCreate, CourseResponse
from app.courses.service import (
    create_course,
    delete_course,
    get_owned_course,
    list_owned_courses,
)

router = APIRouter(prefix="/courses", tags=["courses"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create(
    payload: CourseCreate, user: CurrentUser, session: DatabaseSession
) -> CourseResponse:
    course = await create_course(session, user.id, payload.name)
    return CourseResponse.model_validate(course)


@router.get("", response_model=list[CourseResponse])
async def list_courses(
    user: CurrentUser, session: DatabaseSession
) -> list[CourseResponse]:
    courses = await list_owned_courses(session, user.id)
    return [CourseResponse.model_validate(course) for course in courses]


@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(
    course_id: UUID, user: CurrentUser, session: DatabaseSession
) -> CourseResponse:
    course = await get_owned_course(session, user.id, course_id)
    return CourseResponse.model_validate(course)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_course(
    course_id: UUID, user: CurrentUser, session: DatabaseSession
) -> Response:
    course = await get_owned_course(session, user.id, course_id)
    await delete_course(session, course)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
