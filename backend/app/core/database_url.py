def escape_for_alembic(database_url: str) -> str:
    """Escape percent signs before storing a URL in Alembic's ConfigParser."""

    return database_url.replace("%", "%%")
