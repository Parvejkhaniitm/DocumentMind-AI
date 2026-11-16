from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
EMBEDDING_DIMENSION = 384


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
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_chunk_tokens: int = Field(default=220, gt=0, le=240)
    embedding_chunk_overlap: int = Field(default=40, ge=0, lt=220)
    embedding_batch_size: int = Field(default=32, gt=0, le=128)
    llm_provider: str = "openai_compatible"
    llm_api_key: SecretStr | None = None
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"
    rag_top_k: int = Field(default=6, gt=0, le=20)
    rag_min_relevance: float = Field(default=0.25, ge=-1.0, le=1.0)
    jwt_secret: SecretStr | None = None
    access_token_minutes: int = Field(default=15, gt=0, le=60)
    refresh_token_days: int = Field(default=30, gt=0, le=90)

    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
