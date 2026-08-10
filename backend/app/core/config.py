from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    database_url: str = (
        "postgresql+asyncpg://studypilot:studypilot@localhost:5432/studypilot"
    )
    jwt_secret: str = "change-me-before-deploying"
    jwt_access_token_minutes: int = Field(default=60, gt=0)
    cors_origins: str = "http://localhost:5173"

    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    chat_model: str = "qwen-plus"
    embedding_model: str = "text-embedding-v4"
    embedding_dimension: int = 1024

    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_storage_bucket: str = "course-pdfs"

    max_pdf_bytes: int = 20 * 1024 * 1024
    max_pdf_pages: int = 300
    daily_upload_quota: int = 5
    daily_question_quota: int = 50
    daily_quiz_quota: int = 10
    document_job_timeout_minutes: int = 15

    request_timeout_seconds: float = Field(default=30.0, gt=0)

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
