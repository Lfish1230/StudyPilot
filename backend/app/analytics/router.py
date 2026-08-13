from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.schemas import CourseAnalyticsResponse, MistakeResponse
from app.analytics.service import get_course_analytics, list_mistakes
from app.auth.dependencies import CurrentUser
from app.core.database import get_db_session

router = APIRouter(prefix="/courses/{course_id}", tags=["analytics"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/mistakes", response_model=list[MistakeResponse])
async def get_mistakes(
    course_id: UUID, user: CurrentUser, session: DatabaseSession
) -> list[MistakeResponse]:
    return await list_mistakes(session, user.id, course_id)


@router.get("/analytics", response_model=CourseAnalyticsResponse)
async def analytics(
    course_id: UUID, user: CurrentUser, session: DatabaseSession
) -> CourseAnalyticsResponse:
    return await get_course_analytics(session, user.id, course_id)
