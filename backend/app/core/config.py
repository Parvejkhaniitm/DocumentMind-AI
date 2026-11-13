from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "DocuMind AI API"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://documind:documind@localhost:5432/documind"
    jwt_secret: SecretStr | None = None
    access_token_minutes: int = Field(default=15, gt=0, le=60)
    refresh_token_days: int = Field(default=30, gt=0, le=90)

    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
