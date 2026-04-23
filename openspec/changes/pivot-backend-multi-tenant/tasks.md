## 1. DB 스키마 추가 (Alembic migration)

- [x] 1.1 기존 `backend/app/db/migrations/versions/` 전체 리비전 파일 삭제 (친구용 데이터 보존 가치 없음)
- [x] 1.2 단일 리비전 `001_pivot_multi_tenant.py` 작성 — `tenants`, `shops`, `users`, `refresh_tokens`, `procurement_orders`, `procurement_results` 생성 + `listings.tenant_id` 컬럼 추가
- [x] 1.3 `(tenant_id, created_at DESC)`, `(tenant_id, id)` 복합 인덱스 포함
- [x] 1.4 `alembic upgrade head` 로 로컬 Postgres에 적용 확인 (로컬 Postgres 부재 시 `alembic heads`/`history` 로 단일 head 검증)

## 2. tenancy 모듈 신규

- [x] 2.1 `backend/app/tenancy/__init__.py`
- [x] 2.2 `backend/app/tenancy/models.py` — `Tenant`, `Shop`, `User` SQLAlchemy 모델
- [x] 2.3 `backend/app/tenancy/schemas.py` — Pydantic v2 DTO (`TenantRead`, `TenantCreate`, `ShopRead`, `ShopCreate`, `UserRead`)
- [x] 2.4 `backend/app/tenancy/service.py` — `TenantService`, `ShopService`, `UserService` CRUD (모든 쿼리에 `tenant_id` 필터)
- [x] 2.5 `backend/app/tenancy/dependencies.py` — `get_current_user`, `get_current_tenant` FastAPI 의존성
- [x] 2.6 `backend/app/tenancy/router.py` — `/api/v1/tenants/me`, `/api/v1/shops`, `/api/v1/users` (인증 필요)

## 3. auth 모듈 신규

- [x] 3.1 `backend/app/auth/__init__.py`
- [x] 3.2 `backend/app/auth/models.py` — `RefreshToken(jti, user_id, expires_at, revoked_at)`
- [x] 3.3 `backend/app/auth/schemas.py` — `OAuthCallbackRequest`, `TokenPair`, `RefreshRequest`
- [x] 3.4 `backend/app/auth/jwt.py` — `encode_access_token`, `decode_access_token`, `encode_refresh_token`, `decode_refresh_token` (HS256)
- [x] 3.5 `backend/app/auth/kakao.py` — 카카오 OAuth `authorize_url` 빌더, `exchange_code`, `fetch_userinfo` (httpx)
- [x] 3.6 `backend/app/auth/naver.py` — 네이버 OAuth 동등 구현
- [x] 3.7 `backend/app/auth/service.py` — `AuthService.login_with_kakao/naver`: 프로바이더 userinfo → `find_or_create_tenant_and_user` → JWT 발급
- [x] 3.8 `backend/app/auth/router.py` — `GET /api/v1/auth/{provider}/login`, `GET /api/v1/auth/{provider}/callback`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`
- [x] 3.9 `backend/app/core/security.py` — JWT 인코딩·디코딩 저수준 헬퍼 + 비밀번호 해시 유틸(`bcrypt`)

## 4. procurement 모듈 신규

- [x] 4.1 `backend/app/procurement/__init__.py`
- [x] 4.2 `backend/app/procurement/models.py` — `ProcurementOrder`, `ProcurementResult`
- [x] 4.3 `backend/app/procurement/schemas.py` — `OrderCreate`, `OrderRead`, `ResultUpload`, `ResultRead`, `SummaryReport`
- [x] 4.4 `backend/app/procurement/service.py` — `create_order`, `list_orders`, `upload_result`, `list_results_by_order`, `aggregate_savings`
- [x] 4.5 `backend/app/procurement/router.py` — `POST /orders`, `GET /orders`, `GET /orders/{id}`, `POST /orders/{id}/results`, `GET /orders/{id}/results`, `GET /reports/summary`

## 5. services/search_service.py 재설계

- [x] 5.1 기존 크롤링 오케스트레이션 코드(`_collect_naver`, `_collect_coupang`, `_enrich_details`) 전부 제거
- [x] 5.2 입력을 `tenant_id` + 업로드된 `procurement_results` 로 바꾸고 파서·배송비·랭킹만 수행
- [x] 5.3 응답 캐시 키에 `tenant_id` 네임스페이스 포함 (`search:{tenant_id}:{md5(query|limit)}`)
- [ ] 5.4 테스트 재작성 (`tests/test_services/test_search_service.py`) — Wave 4 에서 처리

## 6. collectors/ 디렉토리 전체 삭제

- [x] 6.1 `backend/app/collectors/` 하위 전체 파일 삭제 (`base.py`, `naver.py`, `naver_detail.py`, `coupang.py`, `coupang_detail.py`, `http_client.py`, `rate_limiter.py`, `circuit_breaker.py`, `selectors.yaml`, `selectors_loader.py`, `remote_scraper.py`, `__init__.py`)
- [x] 6.2 `backend/pyproject.toml` 에서 `playwright`, `selectolax`, `curl_cffi`, `vcrpy`, `respx` 중 크롤러 전용 의존성 제거
- [x] 6.3 import 끊긴 곳(`services/search_service.py` 등) 잔재 참조 전부 제거

## 7. /scraper/ 디렉토리 삭제

- [x] 7.1 `scraper/` 디렉토리 전체 삭제 (Mac mini 용 코드의 레포 내 버전)
- [x] 7.2 `infra/docker-compose.yml` 에서 `scraper` 서비스·볼륨 제거
- [x] 7.3 `.env.example` 에서 `SCRAPER_REMOTE_URL`, `REMOTE_SCRAPER_TOKEN` 같은 설정 제거

## 8. ui/streamlit_app.py 삭제

- [x] 8.1 `backend/app/ui/` 디렉토리 전체 삭제
- [x] 8.2 `backend/pyproject.toml` 에서 `streamlit` 의존성 제거
- [x] 8.3 `infra/docker-compose.yml` 에서 `streamlit` 서비스 제거
- [x] 8.4 `Makefile` 에서 Streamlit 관련 타겟 제거

## 9. core/config.py 업데이트

- [x] 9.1 신규 설정 추가 — `JWT_SECRET`, `JWT_ALGORITHM` (기본 `HS256`), `JWT_ACCESS_TTL_MINUTES` (기본 30), `JWT_REFRESH_TTL_DAYS` (기본 14)
- [x] 9.2 OAuth 설정 추가 — `KAKAO_CLIENT_ID`, `KAKAO_CLIENT_SECRET`, `KAKAO_REDIRECT_URI`, `NAVER_OAUTH_CLIENT_ID`, `NAVER_OAUTH_CLIENT_SECRET`, `NAVER_OAUTH_REDIRECT_URI`
- [x] 9.3 테넌트 설정 추가 — `DEFAULT_TENANT_API_QUOTA_MONTHLY` (기본 10000)
- [x] 9.4 구 설정 제거 — `NAVER_CLIENT_ID`/`NAVER_CLIENT_SECRET` (쇼핑 API 용), `PLAYWRIGHT_CONCURRENCY`, `NAVER_RPM`, `COUPANG_RPM`, `DETAIL_CACHE_TTL_SECONDS`, `SCRAPER_REMOTE_URL`
- [x] 9.5 `.env.example` 동기화

## 10. api/v1/router.py 인증 미들웨어 적용

- [x] 10.1 `api/v1/router.py` 에서 `tenancy.router`, `auth.router`, `procurement.router` 통합
- [x] 10.2 `/api/v1/auth/**`, `/api/v1/health/**` 외 모든 라우트에 `Depends(get_current_tenant)` 의존성 적용
- [x] 10.3 `api/v1/search.py` — `tenant: Annotated[Tenant, Depends(get_current_tenant)]` 인자로 변경, 서비스 호출 시 `tenant_id` 전달
- [x] 10.4 `middleware.py` 에 `tenant_id` 구조화 로그 contextvars 주입 로직 추가 (structlog)

## 11. quota_service.py 재설계 (테넌트별 월간)

- [x] 11.1 기존 `naver:quota:<YYYYMMDD>` 일일 카운터 로직 제거
- [x] 11.2 `quota:tenant:{tenant_id}:{YYYYMM}` 키 + `INCR` + `EXPIREAT` 다음달 1일 00:00 KST
- [x] 11.3 `check_and_consume(tenant_id, monthly_quota)` 메서드 — 초과 시 `QuotaExceededError` 발생
- [x] 11.4 `services/search_service.py`·`procurement/service.py` 업로드 호출 시 훅 연결

## 12. cache_service.py 업데이트

- [x] 12.1 모든 `get`/`set` 시그니처에 `tenant_id: int` 필수 파라미터 추가
- [x] 12.2 캐시 키 네임스페이스를 `"tenant:{tenant_id}:" + key` 형식으로 강제

## 13. option_parser.py 업데이트

- [x] 13.1 입력 소스 docstring/타입 주석을 "크롤러 HTML" → "클라이언트가 업로드한 옵션 텍스트" 로 수정
- [x] 13.2 `option_text_cache` 캐시 조회 시 `tenant_id` 스코프 키 도입 (전역 캐시 vs 테넌트별 — 전역 유지하되 로그 차원에서 `tenant_id` 기록)

## 14. models/listing.py 수정

- [x] 14.1 `tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)` 추가
- [x] 14.2 관계 매핑 추가 (`tenant: Mapped[Tenant] = relationship(...)`)

## 15. 기존 테스트 중 collectors 관련 제거·마이그레이션

- [x] 15.1 `backend/tests/test_collectors/` 디렉토리 전체 삭제
- [x] 15.2 `backend/tests/test_services/test_search_service.py` 에서 크롤링 관련 fixture·목 제거
- [x] 15.3 Streamlit UI 관련 테스트 삭제
- [x] 15.4 `detail_cache_service` 관련 테스트 삭제

## 16. 신규 모듈 테스트 작성

- [ ] 16.1 `backend/tests/test_tenancy/test_models.py` — Tenant/Shop/User CRUD
- [ ] 16.2 `backend/tests/test_tenancy/test_dependencies.py` — `get_current_tenant` 누락·만료·위조 토큰
- [ ] 16.3 `backend/tests/test_tenancy/test_isolation.py` — 테넌트 A 토큰으로 테넌트 B 데이터 조회 시 404 보장 (크로스 테넌트 격리 의무화)
- [ ] 16.4 `backend/tests/test_auth/test_jwt.py` — access/refresh 발급·만료·서명 검증
- [ ] 16.5 `backend/tests/test_auth/test_kakao.py` — `respx` 로 카카오 API 스텁, 토큰 교환·userinfo 플로우
- [ ] 16.6 `backend/tests/test_auth/test_naver.py` — 네이버 OAuth 동등
- [ ] 16.7 `backend/tests/test_auth/test_refresh_rotation.py` — refresh 갱신·revoke
- [ ] 16.8 `backend/tests/test_procurement/test_orders.py` — 발주 생성·조회·테넌트 격리
- [ ] 16.9 `backend/tests/test_procurement/test_results.py` — 결과 업로드·집계
- [ ] 16.10 `backend/tests/test_procurement/test_quota.py` — 테넌트 월간 쿼터 초과 시 429
- [ ] 16.11 `pytest --cov` 으로 새 모듈 커버리지 80% 이상 확인
