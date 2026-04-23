## ADDED Requirements

### Requirement: 카카오 OAuth 2.0 로그인

시스템은 카카오 OAuth 2.0 Authorization Code 플로우를 지원해야 한다(MUST). `GET /api/v1/auth/kakao/login` 은 `state` 파라미터 포함 authorize URL 로 302 리다이렉트하고, `GET /api/v1/auth/kakao/callback?code=...&state=...` 는 토큰 교환·사용자 정보 조회·테넌트/사용자 프로비저닝·JWT 발급을 수행한다.

#### Scenario: 로그인 시작
- **WHEN** 클라이언트가 `GET /api/v1/auth/kakao/login` 을 호출한다
- **THEN** 시스템은 302 응답과 함께 `Location: https://kauth.kakao.com/oauth/authorize?client_id=<KAKAO_CLIENT_ID>&redirect_uri=<KAKAO_REDIRECT_URI>&response_type=code&state=<csrf_token>` 로 리다이렉트한다

#### Scenario: 콜백 정상 처리
- **WHEN** 카카오가 유효한 `code` 로 콜백한다
- **THEN** 시스템은 `POST https://kauth.kakao.com/oauth/token` 으로 토큰 교환, `GET https://kapi.kakao.com/v2/user/me` 로 사용자 정보 조회 후, 해당 `kakao_id` 기준으로 테넌트/사용자를 `find_or_create` 하고 access/refresh JWT 를 발급해 JSON 으로 반환한다

#### Scenario: 카카오 토큰 교환 실패
- **WHEN** 카카오가 `POST /oauth/token` 에 대해 4xx/5xx 로 응답한다
- **THEN** 시스템은 HTTP 502 `{detail: "kakao_token_exchange_failed", code: "UPSTREAM_ERROR"}` 를 반환한다

#### Scenario: 이메일 미동의
- **WHEN** 카카오 사용자 정보 응답에 `kakao_account.email` 이 없거나 동의되지 않았다
- **THEN** 시스템은 HTTP 400 `{detail: "email_consent_required", code: "EMAIL_REQUIRED"}` 를 반환하고 사용자 생성을 거부한다

### Requirement: 네이버 OAuth 2.0 로그인

시스템은 네이버 OAuth 2.0 Authorization Code 플로우를 지원해야 한다(MUST). 엔드포인트 쌍은 `GET /api/v1/auth/naver/login` 과 `GET /api/v1/auth/naver/callback` 이며 카카오와 동일한 시그니처·응답 구조를 가진다.

#### Scenario: 네이버 로그인 시작
- **WHEN** 클라이언트가 `GET /api/v1/auth/naver/login` 을 호출한다
- **THEN** 시스템은 302 응답과 `Location: https://nid.naver.com/oauth2.0/authorize?response_type=code&client_id=<NAVER_OAUTH_CLIENT_ID>&redirect_uri=<NAVER_OAUTH_REDIRECT_URI>&state=<csrf_token>` 로 리다이렉트한다

#### Scenario: 네이버 콜백 정상 처리
- **WHEN** 네이버가 유효한 `code` 로 콜백한다
- **THEN** 시스템은 `POST https://nid.naver.com/oauth2.0/token` 으로 토큰 교환, `GET https://openapi.naver.com/v1/nid/me` 로 사용자 정보 조회 후 카카오와 동일한 `find_or_create` → JWT 발급 절차를 수행한다

### Requirement: JWT Access / Refresh 토큰

시스템은 HS256 서명의 JWT access token 과 refresh token 을 발급해야 한다(MUST). access token TTL 기본값은 30분(`JWT_ACCESS_TTL_MINUTES`), refresh token TTL 기본값은 14일(`JWT_REFRESH_TTL_DAYS`), 서명 키는 `JWT_SECRET` 환경변수다.

#### Scenario: access token 페이로드
- **WHEN** 시스템이 access token 을 발급한다
- **THEN** 페이로드는 `{sub: <user_id>, tenant_id: <tenant_id>, type: "access", iat, exp, jti}` 를 포함한다

#### Scenario: refresh token 저장
- **WHEN** 시스템이 refresh token 을 발급한다
- **THEN** `refresh_tokens(jti, user_id, expires_at, revoked_at=NULL)` 테이블에 레코드를 저장하고 JWT 응답에 포함한다

#### Scenario: refresh token revoke
- **WHEN** 사용자가 로그아웃하거나 관리자가 토큰을 무효화한다
- **THEN** 시스템은 `refresh_tokens.revoked_at` 에 현재 시각을 기록하고, 이후 해당 `jti` 로의 갱신 요청은 모두 거부한다

### Requirement: 토큰 갱신 엔드포인트

시스템은 `POST /api/v1/auth/refresh` 엔드포인트를 제공해야 한다(MUST). 요청 본문의 refresh token 이 유효하고 revoke 되지 않았으며 만료되지 않은 경우, 신규 access token 을 발급해 반환한다.

#### Scenario: 정상 갱신
- **WHEN** 클라이언트가 유효한 refresh token 으로 `POST /api/v1/auth/refresh` 를 호출한다
- **THEN** 시스템은 HTTP 200 `{access_token: <new_access>, refresh_token: <same_or_new_refresh>}` 를 반환한다

#### Scenario: 만료된 refresh token
- **WHEN** 만료된 refresh token 으로 갱신을 요청한다
- **THEN** 시스템은 HTTP 401 `{detail: "refresh_token_expired", code: "UNAUTHORIZED"}` 를 반환한다

#### Scenario: revoke 된 refresh token
- **WHEN** `refresh_tokens.revoked_at` 이 NULL 이 아닌 refresh token 으로 갱신을 요청한다
- **THEN** 시스템은 HTTP 401 `{detail: "refresh_token_revoked", code: "UNAUTHORIZED"}` 를 반환한다

### Requirement: 로그아웃 엔드포인트

시스템은 `POST /api/v1/auth/logout` 엔드포인트를 제공해야 한다(SHALL). 인증된 요청의 refresh token(본문 또는 헤더)을 revoke 한다.

#### Scenario: 로그아웃 정상 처리
- **WHEN** 인증된 사용자가 `POST /api/v1/auth/logout` 을 호출하며 refresh token 을 전달한다
- **THEN** 시스템은 `refresh_tokens.revoked_at` 을 현재 시각으로 갱신하고 HTTP 204 를 반환한다

#### Scenario: 이미 revoke 된 토큰
- **WHEN** 이미 revoke 된 refresh token 으로 로그아웃을 요청한다
- **THEN** 시스템은 HTTP 204 를 반환한다 (멱등)

### Requirement: CSRF 보호 (state 파라미터)

시스템은 OAuth login 진입 시 랜덤 `state` 값을 생성해 Redis (`oauth:state:{value}`, TTL 10분)에 저장하고, 콜백에서 일치 여부를 검증해야 한다(SHALL).

#### Scenario: state 불일치
- **WHEN** 콜백의 `state` 파라미터가 Redis 에 존재하지 않거나 값이 일치하지 않는다
- **THEN** 시스템은 HTTP 400 `{detail: "state_mismatch", code: "CSRF"}` 를 반환한다

#### Scenario: state 정상 검증
- **WHEN** 콜백의 `state` 가 Redis 에서 조회되어 매칭된다
- **THEN** 시스템은 해당 키를 즉시 삭제(one-time use)하고 토큰 교환 단계로 진행한다

### Requirement: 보호된 라우트 인증 통합

시스템은 `/api/v1/auth/**`, `/api/v1/health/**`, `/metrics` 를 제외한 모든 API 라우트에 `Depends(get_current_tenant)` 를 적용해야 한다(MUST).

#### Scenario: 인증 미들웨어 누락 방지
- **WHEN** 신규 라우트가 인증 의존성 없이 추가된다
- **THEN** 통합 테스트는 해당 라우트가 401 을 반환하지 않는 것을 실패로 기록해야 한다 (린트·테스트로 강제)
