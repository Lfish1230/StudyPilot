from configparser import ConfigParser

from app.core.database_url import asyncpg_connect_args, escape_for_alembic


def test_escape_for_alembic_preserves_percent_encoded_password() -> None:
    database_url = (
        "postgresql+asyncpg://user:p%3Dword%21@db.example.com:5432/app"
    )
    parser = ConfigParser()
    parser.add_section("alembic")

    parser.set("alembic", "sqlalchemy.url", escape_for_alembic(database_url))

    assert parser.get("alembic", "sqlalchemy.url") == database_url


def test_transaction_pooler_disables_asyncpg_statement_cache() -> None:
    database_url = "postgresql+asyncpg://user:pass@db.example.com:6543/app"

    assert asyncpg_connect_args(database_url) == {"statement_cache_size": 0}


def test_session_pooler_keeps_default_asyncpg_connection_args() -> None:
    database_url = "postgresql+asyncpg://user:pass@db.example.com:5432/app"

    assert asyncpg_connect_args(database_url) == {}
