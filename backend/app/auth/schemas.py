"""인증 관련 Pydantic v2 DTO."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OAuthCallbackRequest(BaseModel):
    """OAuth 프로바이더 콜백 쿼리스트링."""

    model_config = ConfigDict(extra="ignore")

    code: str = Field(..., min_length=1, description="프로바이더가 발급한 인가 코드")
    state: str = Field(..., min_length=1, description="CSRF 방지용 state 값")


class TokenPair(BaseModel):
    """Access + Refresh 토큰 응답."""

    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="access_token 만료까지 남은 초")


class RefreshRequest(BaseModel):
    """토큰 갱신 요청 본문."""

    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(..., min_length=1)


class LogoutRequest(BaseModel):
    """로그아웃 요청 본문 (refresh token 전달)."""

    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(..., min_length=1)
