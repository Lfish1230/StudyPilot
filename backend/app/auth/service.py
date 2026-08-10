from typing import cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.model import User
from app.core.errors import ConflictError, UnauthorizedError
from app.core.security import hash_password, verify_password


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    return cast(
        User | None,
        await session.scalar(select(User).where(User.email == normalize_email(email))),
    )


async def register_user(session: AsyncSession, email: str, password: str) -> User:
    user = User(
        email=normalize_email(email),
        password_hash=hash_password(password),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("email_already_registered", "该邮箱已经注册。") from exc
    await session.refresh(user)
    return user


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User:
    user = await get_user_by_email(session, email)
    if user is None or not verify_password(password, user.password_hash):
        raise UnauthorizedError("invalid_credentials", "邮箱或密码不正确。")
    return user
