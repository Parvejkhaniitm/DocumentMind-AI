from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "DocuMind AI API"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://documind:documind@localhost:5432/documind"
    redis_url: str = "redis://localhost:6379/0"
    object_storage_endpoint: str = "http://localhost:9000"
    object_storage_bucket: str = "documind"
    object_storage_access_key: SecretStr = SecretStr("minioadmin")
    object_storage_secret_key: SecretStr = SecretStr("minioadmin")
    max_upload_bytes: int = Field(default=20 * 1024 * 1024, gt=0, le=100 * 1024 * 1024)
    max_docx_uncompressed_bytes: int = Field(default=100 * 1024 * 1024, gt=0)
    max_pdf_pages: int = Field(default=500, gt=0, le=5000)
    max_extracted_text_chars: int = Field(default=5_000_000, gt=0)
    jwt_secret: SecretStr | None = None
    access_token_minutes: int = Field(default=15, gt=0, le=60)
    refresh_token_days: int = Field(default=30, gt=0, le=90)

    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
