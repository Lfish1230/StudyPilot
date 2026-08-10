from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.model import User
from app.core.database import get_db_session
from app.core.errors import UnauthorizedError
from app.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    if token is None:
        raise UnauthorizedError("not_authenticated", "请先登录。")
    user_id = decode_access_token(token)
    user = await session.get(User, user_id)
    if user is None:
        raise UnauthorizedError("invalid_token", "登录状态无效，请重新登录。")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
