from configparser import ConfigParser

from app.core.database_url import escape_for_alembic


def test_escape_for_alembic_preserves_percent_encoded_password() -> None:
    database_url = (
        "postgresql+asyncpg://user:p%3Dword%21@db.example.com:5432/app"
    )
    parser = ConfigParser()
    parser.add_section("alembic")

    parser.set("alembic", "sqlalchemy.url", escape_for_alembic(database_url))

    assert parser.get("alembic", "sqlalchemy.url") == database_url
