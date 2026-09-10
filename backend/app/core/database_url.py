from sqlalchemy.engine import make_url


def escape_for_alembic(database_url: str) -> str:
    """Escape percent signs before storing a URL in Alembic's ConfigParser."""

    return database_url.replace("%", "%%")


def asyncpg_connect_args(database_url: str) -> dict[str, int]:
    """Disable asyncpg's statement cache for transaction-pooler connections."""

    if make_url(database_url).port == 6543:
        return {"statement_cache_size": 0}
    return {}
