from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5", alias="OPENAI_MODEL")
    openai_extraction_model: str | None = Field(
        default=None,
        alias="OPENAI_EXTRACTION_MODEL",
    )
    app_name: str = Field(default="ma-mna-analyzer", alias="APP_NAME")
    request_timeout_seconds: float = Field(default=180.0, alias="REQUEST_TIMEOUT_SECONDS")
    connect_timeout_seconds: float = Field(default=20.0, alias="CONNECT_TIMEOUT_SECONDS")
    download_dir: Path = Field(default=Path(".cache/ma_mna_analyzer"), alias="DOWNLOAD_DIR")
    max_search_results: int = Field(default=8, alias="MAX_SEARCH_RESULTS")
    max_crawl_pages: int = Field(default=18, alias="MAX_CRAWL_PAGES")
    max_documents_per_company: int = Field(default=6, alias="MAX_DOCUMENTS_PER_COMPANY")
    max_web_snippets_per_company: int = Field(default=4, alias="MAX_WEB_SNIPPETS_PER_COMPANY")
    max_pdf_bytes: int = Field(default=60_000_000, alias="MAX_PDF_BYTES")
    user_agent: str = Field(
        default="ma-mna-analyzer/0.1 (+https://example.invalid)",
        alias="USER_AGENT",
    )
    verify_ssl: bool = Field(default=True, alias="VERIFY_SSL")
    app_env: str = Field(default="development", alias="APP_ENV")

    model_config = SettingsConfigDict(extra="ignore")

    @property
    def extraction_model(self) -> str:
        return self.openai_extraction_model or self.openai_model


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    if not _is_production_environment():
        load_dotenv(dotenv_path=".env", override=False)
    try:
        settings = Settings()
    except ValidationError as exc:
        raise RuntimeError(
            "Configuration error: OPENAI_API_KEY is required. "
            "Set it via runtime environment variables in production."
        ) from exc
    settings.download_dir.mkdir(parents=True, exist_ok=True)
    return settings


def _is_production_environment() -> bool:
    env = os.getenv("APP_ENV", "development").strip().lower()
    return env in {"prod", "production"}
