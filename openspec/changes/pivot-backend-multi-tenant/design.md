## Context

- 기존 백엔드는 단일 사용자 전제(`friend_mode = true`)로 설계되어 있어, 모든 테이블에 `tenant_id` 개념이 없고, API 엔드포인트는 인증 미들웨어 없이 열려 있다.
- 피벗 후에는 **테넌트(소매점 운영자) → 소매점(shops) → 사용자(users)** 3계층 소유 구조가 필요하며, 모든 데이터 접근이 `tenant_id` 로 격리되어야 한다.
- 크롤링은 **클라이언트(브라우저 확장·Tauri 앱)가 수행**하므로 백엔드에는 `collectors/` 폐기. 백엔드는 클라이언트가 업로드한 DOM 파싱 결과를 받아 정규화·저장·랭킹·리포트만 담당한다.
- 인증은 한국 B2B 시장을 타겟하므로 카카오·네이버 OAuth 2.0 우선. 자체 이메일/패스워드는 예비(`auth_provider = 'local'`)로만 스키마에 존재.

## Goals / Non-Goals

**Goals:**
- 모든 도메인 테이블에 `tenant_id` 컬럼과 row-level 격리 의존성(`Depends(get_current_tenant)`)을 적용해 크로스 테넌트 데이터 유출을 **스키마 레벨에서 방지**한다.
- 카카오·네이버 OAuth 로그인 → 테넌트·사용자 자동 프로비저닝 → JWT access/refresh 발급 파이프라인을 완결한다.
- 기존 파서·랭킹·배송비 정책 코드는 **그대로 재활용**하며, 입력 소스만 클라이언트 업로드로 스위칭한다.
- `/scraper/`·`collectors/`·`ui/streamlit_app.py`·`services/detail_cache_service.py` 를 완전 삭제해 법적·기술적 리스크의 코드 경로를 제거한다.

**Non-Goals:**
- 구독 결제·인보이스·쿠폰: 영역 D 제안. 본 영역은 `tenants.plan` 컬럼과 `api_quota_monthly` 필드만 준비.
- 관리자 대시보드·관측성 강화: 영역 E 제안.
- 스키마당 격리(schema-per-tenant), DB당 격리(database-per-tenant): 초기에는 row-level 로 충분. 대형 테넌트가 붙으면 재평가.
- 브라우저 확장·Tauri 앱 구현: 영역 B·C 제안.
- 자체 이메일/패스워드 로그인 UI: 스키마에만 `auth_provider = 'local'` 자리 예약. 실제 라우트는 추가하지 않는다.

## Decisions

### 1. Tenant 격리 전략: Row-Level Security (RLS) 이전 단계 — 애플리케이션 레벨 격리 우선

- **선택**: `Depends(get_current_tenant)` 로 추출한 `tenant_id` 를 서비스 레이어의 모든 쿼리에 `WHERE tenant_id = :tid` 로 강제.
- **이유**: PostgreSQL RLS 는 마이그레이션 난이도·디버깅 비용이 크고, 초기 테넌트 수가 적어 애플리케이션 레벨이 충분. 모든 서비스 메서드 시그니처에 `tenant_id: int` 를 필수 인자로 두어 누락 시 타입 체크로 실패.
- **대안**: PostgreSQL RLS (`ALTER TABLE ... ENABLE ROW LEVEL SECURITY`, `CURRENT_SETTING('app.tenant_id')`) — 장점: 백업·쿼리 누수 방어. 단점: Alembic 관리 복잡, psycopg/asyncpg 에서 `SET LOCAL` 호출 오버헤드.
- **향후**: 테넌트 100+ 또는 감사 요구 시 RLS 로 점진 전환. 컬럼·인덱스는 이미 `tenant_id` 기반이라 무중단 마이그레이션 가능.

### 2. 인증: OAuth 2.0 Authorization Code + JWT

- **OAuth 프로바이더**: 카카오(kakao), 네이버(naver) 2종. 카카오/네이버 모두 공식 Authorization Code 플로우 지원.
- **토큰**: access token JWT(HS256, 30분) + refresh token JWT(HS256, 14일). refresh token 은 DB `refresh_tokens(jti, user_id, expires_at, revoked_at)` 에 저장해 revoke 가능.
- **`Depends(get_current_tenant)`**: `Authorization: Bearer <access>` 헤더를 디코드 → `user_id` → `user.tenant_id` 조회 → 요청 상태에 주입. 미로그인 접근은 `HTTPException(401)`.
- **대안 고려**:
  - 세션 쿠키 기반: Tauri 데스크톱 클라이언트·브라우저 확장에서 쿠키 관리 복잡. 배제.
  - OAuth access token 그대로 사용: 프로바이더별 토큰 라이프사이클이 달라 refresh 로직이 분산됨. JWT 로 통일.

### 3. OAuth 프로바이더 라이브러리

- **선택**: `httpx` 로 직접 호출 + 경량 래퍼(`backend/app/auth/kakao.py`, `naver.py`). 토큰 교환·사용자 정보 조회 각 1회 호출로 의존성 최소화.
- **대안**: `httpx-oauth`, `authlib` — 훅·이벤트 추상화 과도. 네이티브 API 2종만 지원하므로 경량 구현이 유지보수성 유리.
- **교차검증 필요**: 카카오 공식 문서 `https://developers.kakao.com/docs/latest/ko/kakaologin/rest-api`, 네이버 `https://developers.naver.com/docs/login/api/api.md` 의 현행 엔드포인트·스코프. `[교차검증 필요]` — 구현 전 공식 문서 직접 확인.

### 4. 테넌트 자동 프로비저닝

- **최초 OAuth 로그인** 시 해당 이메일/사업자번호로 기존 테넌트가 없으면 `tenants` 1건 + `users` 1건(role=owner) 자동 생성.
- **소매점(`shops`) 등록**: OAuth 로그인 후 온보딩 화면에서 테넌트 오너가 수동으로 추가. 자동 생성 안 함(사업자번호 검증 필요).
- **초대 플로우**: 테넌트 오너가 직원을 초대하면 `users.role = 'staff'` 로 추가. 초대 링크 스펙은 본 영역 외(영역 B 클라이언트 UX).

### 5. 할당량(Quota) 관리 재설계

- **기존**: `quota_service.py` 가 `naver:quota:<YYYYMMDD>` 일일 카운터 관리 → 폐기 대상 크롤링 전용.
- **신규**: 테넌트별 월간 API 호출 쿼터. Redis 키 `quota:tenant:{tenant_id}:{YYYYMM}` + `INCR` + `EXPIREAT <다음달 1일 00:00 KST>`.
- **초과 시 동작**: HTTP 429 + `{detail: "tenant_quota_exceeded", code: "QUOTA_EXCEEDED"}`. Plan 업그레이드 유도는 영역 D 책임.

### 6. Schema-per-tenant 대비 인덱스 설계

- 모든 테넌트 격리 테이블은 `(tenant_id, created_at DESC)` 복합 인덱스 + `(tenant_id, id)` 고유 인덱스를 둔다.
- 조인 쿼리는 항상 `tenant_id` 를 조인 조건에 포함 — 테이블 전체 스캔 방지.

### 7. Migration 전략: 깨끗한 schema 재생성

- 기존 데이터(친구용)는 보존 가치 없음(친구 3-5명, 다년치 데이터 아님).
- `alembic downgrade base` → 기존 리비전 파일 삭제 → 신규 단일 리비전 `001_pivot_multi_tenant.py` 작성.
- 다운타임은 일시적으로 허용(친구 대상 공지).

### 8. 재활용 모듈 매핑

| 기존 경로 | 피벗 후 경로 | 변경 |
|---|---|---|
| `backend/app/parsers/regex_parser.py` | 동일 | 없음 (REUSE) |
| `backend/app/parsers/unit_dictionary.py` | 동일 | 없음 (REUSE) |
| `backend/app/parsers/unit_price.py` | 동일 | 없음 (REUSE) |
| `backend/app/parsers/option_parser.py` | 동일 | 입력 소스 주석만 갱신 (MODIFY) |
| `backend/app/parsers/llm_parser.py` | 동일 | OpenAI 유지 (MODIFY, 이미 Ollama 제거됨) |
| `backend/app/services/ranking_service.py` | 동일 | 없음 (REUSE) |
| `backend/app/services/shipping_policy.py` | 동일 | 없음 (REUSE) |
| `backend/app/services/cache_service.py` | 동일 | 캐시 키 네임스페이스에 `tenant_id` 포함 (MODIFY) |
| `backend/app/services/quota_service.py` | 동일 | 플랫폼별 → 테넌트별 재설계 (MODIFY) |
| `backend/app/services/search_service.py` | 동일 | 크롤링 제거, 업로드 기반으로 재설계 (MODIFY) |
| `backend/app/services/detail_cache_service.py` | 삭제 | 크롤링 전제이므로 폐기 (DISCARD) |
| `backend/app/models/base.py` | 동일 | 없음 (REUSE) |
| `backend/app/models/listing.py` | 동일 | `tenant_id` 외래키 추가 (MODIFY) |
| `backend/app/models/option_cache.py` | 동일 | 없음 (REUSE) |
| `backend/app/api/v1/router.py` | 동일 | 인증 미들웨어 적용 (MODIFY) |
| `backend/app/api/v1/search.py` | 동일 | `Depends(get_current_tenant)` 추가 (MODIFY) |
| `backend/app/collectors/**` | 삭제 | 825줄 전체 폐기 (DISCARD) |
| `backend/app/ui/streamlit_app.py` | 삭제 | Tauri 앱이 대체 (DISCARD) |
| `/scraper/` | 삭제 | Mac mini 코드 폐기 (DISCARD) |

### 9. 신규 모듈 구조

```
backend/app/
  core/
    config.py (MODIFIED) — OAuth/JWT/테넌트 설정
    security.py (NEW) — JWT encode/decode, password hash 헬퍼
    logging.py (REUSE)
    middleware.py (MODIFIED) — correlation_id 외에 tenant_id context 주입
  tenancy/ (NEW)
    __init__.py
    models.py — Tenant, Shop, User
    schemas.py — Pydantic DTO
    service.py — CRUD + row-level 격리 헬퍼
    router.py — /api/v1/tenants, /api/v1/shops, /api/v1/users (모두 인증 필요)
    dependencies.py — get_current_tenant, get_current_user
  auth/ (NEW)
    __init__.py
    kakao.py — 카카오 OAuth authorize/callback/userinfo
    naver.py — 네이버 OAuth authorize/callback/userinfo
    jwt.py — access/refresh 발급·검증
    service.py — 로그인·회원가입·토큰 갱신·로그아웃
    router.py — /api/v1/auth/kakao/login, /callback, /api/v1/auth/refresh, /logout
    schemas.py
    models.py — RefreshToken(jti, user_id, expires_at, revoked_at)
  procurement/ (NEW)
    __init__.py
    models.py — ProcurementOrder, ProcurementResult
    schemas.py
    service.py — 발주 생성·조회, 결과 업로드·집계
    router.py — /api/v1/procurement/orders, /api/v1/procurement/results
  parsers/ (REUSE 전체)
  services/
    ranking_service.py (REUSE)
    shipping_policy.py (REUSE)
    cache_service.py (MODIFY — tenant_id 네임스페이스)
    quota_service.py (MODIFY — 테넌트별 월간 쿼터)
    search_service.py (MODIFY — 업로드 결과 랭킹)
  models/
    base.py (REUSE)
    listing.py (MODIFY — tenant_id FK)
    option_cache.py (REUSE)
  api/v1/
    router.py (MODIFY — 인증 미들웨어)
    search.py (MODIFY — get_current_tenant 의존)
    procurement.py (NEW — 발주 라우터 집계)
    health.py (REUSE)
  db/
    session.py (REUSE)
    redis.py (REUSE)
    migrations/
      versions/
        001_pivot_multi_tenant.py (NEW — 기존 리비전 대체)

# 삭제
# backend/app/collectors/**
# backend/app/ui/
# backend/app/services/detail_cache_service.py
# scraper/
```

## DB 스키마 전체

```sql
-- 테넌트(소매점 운영 법인/개인)
CREATE TABLE tenants (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    plan VARCHAR(32) NOT NULL DEFAULT 'starter', -- starter/pro/enterprise
    api_quota_monthly INT NOT NULL DEFAULT 10000,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_tenants_plan ON tenants(plan);

-- 소매점(테넌트가 운영하는 점포. 한 테넌트가 여러 매장 운영 가능)
CREATE TABLE shops (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    business_number VARCHAR(20),  -- 사업자등록번호(선택, 중복 허용)
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_shops_tenant ON shops(tenant_id, created_at DESC);

-- 사용자(테넌트 소속)
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    auth_provider VARCHAR(32) NOT NULL, -- kakao/naver/local
    provider_user_id VARCHAR(255) NOT NULL, -- 프로바이더별 고유 id
    role VARCHAR(32) NOT NULL DEFAULT 'owner', -- owner/staff
    password_hash VARCHAR(255), -- local 프로바이더 전용, 그 외 NULL
    last_login_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE (auth_provider, provider_user_id)
);
CREATE INDEX idx_users_tenant ON users(tenant_id, created_at DESC);
CREATE INDEX idx_users_email ON users(email);

-- Refresh 토큰(revoke 가능)
CREATE TABLE refresh_tokens (
    jti UUID PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id, expires_at DESC);

-- 발주 주문(소매점이 특정 시점에 구매하려는 SKU 리스트)
CREATE TABLE procurement_orders (
    id BIGSERIAL PRIMARY KEY,
    shop_id BIGINT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, -- 비정규화(격리 쿼리용)
    items JSONB NOT NULL, -- [{sku, keyword, target_qty, ...}]
    status VARCHAR(32) NOT NULL DEFAULT 'pending', -- pending/collecting/done/error
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_procurement_orders_tenant ON procurement_orders(tenant_id, created_at DESC);
CREATE INDEX idx_procurement_orders_shop ON procurement_orders(shop_id, created_at DESC);

-- 발주 결과(클라이언트가 업로드한 플랫폼별 상품 데이터)
CREATE TABLE procurement_results (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES procurement_orders(id) ON DELETE CASCADE,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, -- 비정규화
    platform VARCHAR(32) NOT NULL, -- naver/coupang/11st/...
    product_data JSONB NOT NULL, -- {raw_title, options, shipping, price, ...}
    savings_krw INT, -- 옵션가·배송비 기반 절감액(선택)
    fetched_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_procurement_results_order ON procurement_results(order_id, fetched_at DESC);
CREATE INDEX idx_procurement_results_tenant ON procurement_results(tenant_id, fetched_at DESC);
CREATE INDEX idx_procurement_results_platform ON procurement_results(tenant_id, platform, fetched_at DESC);

-- 기존 listings 테이블 확장
ALTER TABLE listings ADD COLUMN tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE;
CREATE INDEX idx_listings_tenant ON listings(tenant_id, created_at DESC);

-- (영역 D 가 별도 제안) subscriptions 테이블은 예약만
-- CREATE TABLE subscriptions ( id BIGSERIAL PRIMARY KEY, tenant_id BIGINT ... );
-- tenants.plan 컬럼이 subscription 현황의 캐시 역할
```

## 인증 플로우

### OAuth 로그인 (예: 카카오)

```
Client (Tauri)                 Backend (/api/v1/auth/kakao)        Kakao
     |                                    |                           |
     |  GET /login                        |                           |
     |----------------------------------->|                           |
     |                                    |  build kakao_authorize_url|
     |  302 Redirect to kakao_authorize_url-------------------------->|
     |                                                                |
     |  <user signs in on kakao.com>                                 |
     |                                                                |
     |  GET /callback?code=XYZ            |                           |
     |<---------------------------------------------------------------|
     |----------------------------------->|  POST /oauth/token        |
     |                                    |-------------------------->|
     |                                    |  {access_token, ...}      |
     |                                    |<--------------------------|
     |                                    |  GET /v2/user/me          |
     |                                    |-------------------------->|
     |                                    |  {kakao_id, email, ...}   |
     |                                    |<--------------------------|
     |                                    |                           |
     |  << find_or_create(tenant, user) >>|                           |
     |                                    |                           |
     |  200 {access_jwt, refresh_jwt}     |                           |
     |<-----------------------------------|                           |
```

### 인증된 API 호출

```
Client                 Backend
  |  GET /api/v1/procurement/orders
  |  Authorization: Bearer <access_jwt>
  |----------------------------------------->|
  |                    | get_current_tenant(request):
  |                    |   - decode access_jwt
  |                    |   - lookup user.tenant_id
  |                    |   - check tenant.plan quota
  |                    |   - inject into request.state.tenant_id
  |                    | service.list_orders(tenant_id=...)
  |                    |   WHERE tenant_id = :tid
  |  200 [{order1}, {order2}]                |
  |<-----------------------------------------|
```

### 토큰 갱신

```
Client
  |  POST /api/v1/auth/refresh
  |  Body: {refresh_token: "<jwt>"}
  |----------------------------------------->|
  |                    | decode refresh_jwt, validate jti NOT revoked
  |                    | issue new access_jwt
  |                    | (optional) rotate refresh_jwt (revoke old)
  |  200 {access_jwt, refresh_jwt?}           |
  |<-----------------------------------------|
```

## FastAPI 의존성 주입 패턴

```python
# backend/app/tenancy/dependencies.py
from typing import Annotated
from fastapi import Depends, HTTPException, status, Request
from backend.app.auth.jwt import decode_access_token
from backend.app.tenancy.service import TenantService

async def get_current_user(
    request: Request,
    tenant_service: Annotated[TenantService, Depends(TenantService.from_request)],
) -> User:
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing_bearer")
    token = authorization.removeprefix("Bearer ")
    try:
        payload = decode_access_token(token)
    except ValueError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_token") from e
    user = await tenant_service.get_user(payload["sub"])
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user_not_found")
    return user

async def get_current_tenant(
    user: Annotated[User, Depends(get_current_user)],
    tenant_service: Annotated[TenantService, Depends(TenantService.from_request)],
) -> Tenant:
    tenant = await tenant_service.get_tenant(user.tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "tenant_not_found")
    return tenant
```

라우트는 아래 패턴으로 통일:

```python
# backend/app/api/v1/procurement.py
from fastapi import APIRouter, Depends
from typing import Annotated

router = APIRouter(prefix="/procurement", tags=["procurement"])

@router.get("/orders", response_model=list[OrderRead])
async def list_orders(
    tenant: Annotated[Tenant, Depends(get_current_tenant)],
    service: Annotated[ProcurementService, Depends(ProcurementService.from_request)],
    limit: int = 50,
    offset: int = 0,
) -> list[OrderRead]:
    return await service.list_orders(tenant_id=tenant.id, limit=limit, offset=offset)
```

## 아키텍처 다이어그램 (텍스트)

```
+-------------------+       +-------------------+        +-------------+
| Tauri Desktop App | <---> | FastAPI Backend   | <----> | PostgreSQL  |
| Browser Extension |       |                   |        +-------------+
+-------------------+       |  /api/v1/auth/*   |
           |                |  /api/v1/tenants  |        +-------------+
           | (OAuth)        |  /api/v1/shops    | <----> |  Redis      |
           v                |  /api/v1/procure* |        +-------------+
+-------------------+       |                   |
| Kakao / Naver     |       |  JWT middleware   |
| OAuth Providers   | <---> |  row-level filter |
+-------------------+       +-------------------+

Client-side:
  - 로그인: OAuth 플로우 → JWT 수령·로컬 저장(OS keychain)
  - 수집: 테넌트 직원이 쿠팡/네이버에 로그인된 세션에서 DOM 파싱
  - 업로드: POST /api/v1/procurement/results 로 JSON 전송
  - 조회: 발주·리포트 데이터 주기적 fetch

Backend:
  - 크롤링 없음. DB 쓰기/읽기 + 정규화 + 랭킹
  - 테넌트별 월간 API 쿼터 enforcement
  - row-level 격리(WHERE tenant_id = :tid)
```

## 기존 모듈 재활용 매핑 (요약)

- **그대로 재사용**: 파서 전체(`regex_parser.py`, `unit_dictionary.py`, `unit_price.py`), `ranking_service.py`, `shipping_policy.py`, `models/base.py`, `models/option_cache.py`
- **시그니처만 수정**: `option_parser.py`, `cache_service.py`(tenant_id 네임스페이스), `quota_service.py`(테넌트별 월간)
- **완전 재설계**: `search_service.py`(크롤링 → 업로드 기반), `api/v1/search.py`(get_current_tenant), `api/v1/router.py`(인증 미들웨어), `core/config.py`(OAuth·JWT 설정)
- **삭제**: `collectors/`(전체), `ui/streamlit_app.py`, `services/detail_cache_service.py`, `/scraper/`

## Risks / Trade-offs

- **카카오·네이버 OAuth 스펙 변경**: `[교차검증 필요]` 두 프로바이더 모두 안정적이지만 스코프·엔드포인트가 연 1-2회 마이너 변경. → 구현 직전 공식 문서 확인, 토큰 교환 URL을 `core/config.py` 환경변수로 외부화.
- **row-level 격리 누락으로 크로스 테넌트 유출**: 서비스 메서드의 `tenant_id: int` 필수 인자 누락이 가장 큰 위험. → 린트 룰 추가(`# type: ignore` 금지 조합), 통합 테스트에서 "다른 테넌트의 데이터는 절대 응답에 포함되지 않는다" 시나리오 의무화.
- **JWT 시크릿 유출**: `JWT_SECRET` 은 환경변수, 컨테이너 재시작 시 모든 refresh token 무효화. → 프로덕션에서는 KMS·Vault 로 관리(영역 E 책임).
- **카카오/네이버 OAuth 등록에 사업자 정보 필요**: 개발 단계에서는 로컬 프로바이더(`auth_provider='local'`)로 스텁. 상용 오픈 전 사업자 등록 필수.
- **기존 친구용 데이터 손실**: Migration 전략이 "버리고 시작"이므로 친구 데이터 전부 삭제. → README 공지 + 기존 `main@c4a8b2b` 태그에서 계속 사용 가능하게 안내.
- **테넌트 월간 쿼터 설계 보수성**: Starter 10k/월 은 추정치. 실사용 프로파일 관측 후 조정 필요.

## Migration Plan

1. **공지**: 기존 친구 사용자에게 "YYYY-MM-DD 부로 피벗, 기존 데이터 삭제" 고지.
2. **브랜치**: `feature/retail-procurement-pivot` (이미 존재).
3. **DB drop & 재생성**:
   - `alembic downgrade base` → 기존 리비전 파일 전체 삭제
   - 단일 신규 리비전 `001_pivot_multi_tenant.py` 작성 (위 DDL 전체 포함)
   - `docker compose down -v` → `docker compose up -d postgres redis` → `alembic upgrade head`
4. **코드 제거 순서(Phase 3 책임)**:
   1. `backend/app/collectors/**` 디렉토리 삭제
   2. `/scraper/` 디렉토리 삭제
   3. `backend/app/ui/streamlit_app.py`·`ui/` 삭제
   4. `backend/app/services/detail_cache_service.py` 삭제
   5. 기존 리비전 파일 전체 삭제 → 단일 리비전 재생성
   6. 기존 테스트 중 collectors/streamlit/detail_cache 종속 테스트 삭제
5. **신규 모듈 추가 순서(Phase 3 책임)**:
   1. `tenancy/` (models, service, dependencies, router)
   2. `auth/` (kakao, naver, jwt, service, router)
   3. `procurement/` (models, service, router)
   4. `core/security.py` (JWT 유틸)
   5. `core/config.py` 업데이트
   6. `api/v1/router.py` 인증 미들웨어 적용
   7. `services/search_service.py`, `services/quota_service.py`, `parsers/option_parser.py`, `models/listing.py` 수정
6. **테스트**:
   1. 신규 모듈 단위 테스트
   2. OAuth 목(mock) 통합 테스트 (kakao/naver API 응답을 `respx` 로 스텁)
   3. 크로스 테넌트 격리 시나리오 테스트 (테넌트 A 토큰으로 테넌트 B 데이터 조회 시 404 보장)
7. **롤백**: `git revert` → `alembic downgrade base`. 기존 친구용 코드는 `main@c4a8b2b` 태그에서 계속 사용 가능.

## Open Questions

- 카카오·네이버 OAuth 서비스 등록 시 필요한 사업자등록증·개인정보처리방침 URL — 상용 배포 시점까지 영역 E 에서 준비. 개발 단계에서는 dev 키 발급으로 진행. `[교차검증 필요]`
- 테넌트 월간 쿼터 10k/50k/무제한 는 추정치. 초기 3개월 운영 후 실데이터로 재조정.
- `auth_provider = 'local'` (이메일/패스워드) 의 실제 로그인 라우트 구현 시점 — 본 영역에서는 스키마만 예약, 실제 라우트는 베타 전환 시 별도 스펙.
- `procurement_results.savings_krw` 의 계산 로직 — 테넌트가 업로드한 동일 SKU 여러 플랫폼 중 최저가 대비 차액? 아니면 기준가 대비 차액? 영역 B 와 협의 필요.
- 카카오 `email` scope 가 사용자가 미동의 시 null 반환 — 로그인은 허용하되 `users.email` 을 nullable 로 둘 것인지, email 필수 거부할 것인지. → 현재 설계는 필수 거부(스키마 `NOT NULL`). 사용자가 이메일 제공 거부 시 회원가입 실패 화면.
