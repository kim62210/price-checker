"""애플리케이션 환경 설정."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    naver_client_id: SecretStr = Field(..., description="네이버 개발자센터 애플리케이션 Client ID")
    naver_client_secret: SecretStr = Field(..., description="네이버 Client Secret")
    naver_rpm: int = Field(default=30, ge=1, le=600)
    naver_daily_quota: int = Field(default=25_000, ge=1)
    coupang_rpm: int = Field(default=10, ge=1, le=600)
    coupang_scraper_url: str = Field(
        default="http://100.70.111.100:8081",
        description="Mac mini CDP 기반 쿠팡 스크레이퍼 엔드포인트 (Tailnet)",
    )
    coupang_scraper_timeout_seconds: float = Field(default=45.0, ge=1.0, le=120.0)

    database_url: str = Field(default="postgresql+asyncpg://lowestprice:lowestprice@localhost:5432/lowestprice")
    redis_url: str = Field(default="redis://localhost:6379/0")

    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="qwen2.5:7b")
    openai_api_key: SecretStr | None = None
    openai_model: str = Field(default="gpt-4o-mini")
    llm_monthly_token_cap: int = Field(default=2_000_000, ge=0)

    search_cache_ttl_seconds: int = Field(default=600, ge=0)
    detail_cache_ttl_seconds: int = Field(default=6 * 3600, ge=0)
    option_cache_ttl_seconds: int = Field(default=24 * 3600, ge=0)

    playwright_concurrency: int = Field(default=2, ge=1, le=16)
    request_jitter_min_ms: int = Field(default=500, ge=0)
    request_jitter_max_ms: int = Field(default=2_000, ge=0)

    parser_version: int = Field(default=1, ge=1)

    sentry_dsn: str | None = None
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    environment: Literal["local", "staging", "prod"] = "local"

    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000, ge=1, le=65535)
    cors_allow_origins: str = Field(default="http://localhost:8501")

    @property
    def cors_allow_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
