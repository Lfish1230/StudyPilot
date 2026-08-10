import asyncio
import os
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command

TEST_DATABASE_URL = (
    "postgresql+asyncpg://studypilot:studypilot@localhost:5432/studypilot_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["JWT_SECRET"] = "test-only-secret-that-is-long-enough"
os.environ["ENVIRONMENT"] = "testing"

from app.core.database import SessionLocal  # noqa: E402
from app.main import create_app  # noqa: E402


async def ensure_test_database() -> None:
    connection = await asyncpg.connect(
        user="studypilot",
        password="studypilot",
        host="127.0.0.1",
        port=5432,
        database="studypilot",
    )
    try:
        exists = await connection.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = 'studypilot_test'"
        )
        if exists is None:
            await connection.execute("CREATE DATABASE studypilot_test")
    finally:
        await connection.close()


async def clear_users() -> None:
    async with SessionLocal() as session:
        await session.execute(text("TRUNCATE TABLE users CASCADE"))
        await session.commit()


@pytest.fixture(scope="session", autouse=True)
def migrated_test_database() -> Iterator[None]:
    asyncio.run(ensure_test_database())
    alembic_config = Config("alembic.ini")
    command.upgrade(alembic_config, "head")
    yield


@pytest.fixture(autouse=True)
def clean_database(migrated_test_database: None) -> Iterator[None]:
    del migrated_test_database
    asyncio.run(clear_users())
    yield
    asyncio.run(clear_users())


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


@dataclass(frozen=True)
class CreatedUser:
    id: str
    email: str
    password: str


@pytest.fixture
def user_factory(client: TestClient) -> Callable[..., CreatedUser]:
    def create_user(
        email: str | None = None, password: str = "correct-horse-42"
    ) -> CreatedUser:
        chosen_email = email or f"student-{uuid4()}@example.com"
        response = client.post(
            "/auth/register",
            json={"email": chosen_email, "password": password},
        )
        assert response.status_code == 201
        payload = response.json()
        return CreatedUser(payload["id"], payload["email"], password)

    return create_user


@pytest.fixture
def token_for(client: TestClient) -> Callable[[CreatedUser], dict[str, str]]:
    def make_headers(user: CreatedUser) -> dict[str, str]:
        response = client.post(
            "/auth/login",
            json={"email": user.email, "password": user.password},
        )
        assert response.status_code == 200
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return make_headers


@pytest.fixture
def auth_headers(
    user_factory: Callable[..., CreatedUser],
    token_for: Callable[[CreatedUser], dict[str, str]],
) -> dict[str, str]:
    return token_for(user_factory())
