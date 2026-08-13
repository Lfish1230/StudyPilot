"""Idempotently create the deployment demo user and its sample course."""

import asyncio
import os

from sqlalchemy import select

from app.auth.service import get_user_by_email, register_user
from app.core.database import SessionLocal
from app.courses.model import Course
from app.courses.service import create_course


def required_environment(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be set")
    return value


async def seed_demo() -> None:
    email = required_environment("DEMO_EMAIL")
    password = required_environment("DEMO_PASSWORD")
    course_name = os.getenv("DEMO_COURSE_NAME", "计算机网络 · 演示课程").strip()
    if not course_name:
        raise RuntimeError("DEMO_COURSE_NAME must not be blank")

    async with SessionLocal() as session:
        user = await get_user_by_email(session, email)
        if user is None:
            user = await register_user(session, email, password)
            print(f"Created demo user: {user.email}")
        else:
            print(f"Demo user already exists: {user.email}")

        course = await session.scalar(
            select(Course).where(
                Course.owner_id == user.id,
                Course.name == course_name,
            )
        )
        if course is None:
            course = await create_course(session, user.id, course_name)
            print(f"Created demo course: {course.name}")
        else:
            print(f"Demo course already exists: {course.name}")


if __name__ == "__main__":
    asyncio.run(seed_demo())
