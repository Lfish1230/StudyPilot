from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.courses.model import Course


async def get_owned_course(
    session: AsyncSession, user_id: UUID, course_id: UUID
) -> Course:
    course = await session.scalar(
        select(Course).where(
            Course.id == course_id,
            Course.owner_id == user_id,
        )
    )
    if course is None:
        raise NotFoundError("course_not_found", "课程不存在。")
    return course


async def create_course(session: AsyncSession, owner_id: UUID, name: str) -> Course:
    course = Course(owner_id=owner_id, name=name.strip())
    session.add(course)
    await session.commit()
    await session.refresh(course)
    return course


async def list_owned_courses(session: AsyncSession, owner_id: UUID) -> list[Course]:
    courses = await session.scalars(
        select(Course)
        .where(Course.owner_id == owner_id)
        .order_by(Course.created_at.desc(), Course.id.desc())
    )
    return list(courses)


async def delete_course(session: AsyncSession, course: Course) -> None:
    await session.delete(course)
    await session.commit()
