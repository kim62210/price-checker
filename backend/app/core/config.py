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

    database_url: str = Field(default="postgresql+asyncpg://lowestprice:lowestprice@localhost:5432/lowestprice")
    redis_url: str = Field(default="redis://localhost:6379/0")

    openai_api_key: SecretStr | None = None
    openai_model: str = Field(default="gpt-4o-mini")
    llm_monthly_token_cap: int = Field(default=2_000_000, ge=0)

    search_cache_ttl_seconds: int = Field(default=600, ge=0)
    option_cache_ttl_seconds: int = Field(default=24 * 3600, ge=0)

    request_jitter_min_ms: int = Field(default=500, ge=0)
    request_jitter_max_ms: int = Field(default=2_000, ge=0)

    parser_version: int = Field(default=1, ge=1)

    sentry_dsn: str | None = None
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    environment: Literal["local", "staging", "prod"] = "local"

    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000, ge=1, le=65535)
    cors_allow_origins: str = Field(default="http://localhost:3000")

    # ----- JWT -----
    jwt_secret: SecretStr = Field(
        default=SecretStr("change-me-in-prod"),
        description="JWT HS256 서명 시크릿 (프로덕션 필수 재정의)",
    )
    jwt_algorithm: Literal["HS256"] = Field(default="HS256")
    jwt_access_ttl_minutes: int = Field(default=30, ge=1)
    jwt_refresh_ttl_days: int = Field(default=14, ge=1)

    # ----- OAuth: Kakao -----
    kakao_client_id: SecretStr = Field(
        default=SecretStr(""), description="카카오 REST API 키"
    )
    kakao_client_secret: SecretStr = Field(
        default=SecretStr(""), description="카카오 Client Secret (선택)"
    )
    kakao_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/auth/kakao/callback",
        description="카카오 OAuth 콜백 URL",
    )

    # ----- OAuth: Naver -----
    naver_oauth_client_id: SecretStr = Field(
        default=SecretStr(""), description="네이버 로그인 애플리케이션 Client ID"
    )
    naver_oauth_client_secret: SecretStr = Field(
        default=SecretStr(""), description="네이버 로그인 Client Secret"
    )
    naver_oauth_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/auth/naver/callback",
        description="네이버 OAuth 콜백 URL",
    )

    # ----- Tenant defaults -----
    default_tenant_api_quota_monthly: int = Field(default=10_000, ge=0)

    # ----- Notifications -----
    notification_provider_mode: Literal["fake", "sandbox", "production"] = "fake"
    notification_retry_max_attempts: int = Field(default=3, ge=1)
    notification_retry_base_seconds: int = Field(default=60, ge=1)
    notification_quota_monthly: int = Field(default=1_000, ge=0)
    notification_webhook_secret: SecretStr = Field(default=SecretStr(""))
    kakao_bizmessage_api_url: str = Field(default="")
    kakao_bizmessage_api_key: SecretStr = Field(default=SecretStr(""))
    kakao_sender_profile_key: SecretStr = Field(default=SecretStr(""))
    sms_provider_api_url: str = Field(default="")
    sms_provider_api_key: SecretStr = Field(default=SecretStr(""))
    sms_default_sender_phone: str = Field(default="")

    @property
    def cors_allow_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
