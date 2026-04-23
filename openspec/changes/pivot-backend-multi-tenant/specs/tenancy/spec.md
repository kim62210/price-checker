## ADDED Requirements

### Requirement: 테넌트 엔티티 관리

시스템은 `tenants(id, name, plan, api_quota_monthly, created_at, updated_at)` 테이블로 테넌트(소매점 운영 주체)를 관리해야 한다(MUST). `name` 은 UNIQUE 제약을 가지며, `plan` 은 `starter`/`pro`/`enterprise` 중 하나이고 기본값은 `starter`, `api_quota_monthly` 의 기본값은 10000 이다.

#### Scenario: 테넌트 최초 생성
- **WHEN** OAuth 로그인 후 해당 프로바이더 사용자 id 로 기존 테넌트가 없다
- **THEN** 시스템은 `name = "<provider>_<provider_user_id>"` 형식으로 `tenants` 레코드를 1건 생성하고 `plan = 'starter'`, `api_quota_monthly = DEFAULT_TENANT_API_QUOTA_MONTHLY` 를 적용한다

#### Scenario: 테넌트 정보 조회
- **WHEN** 인증된 사용자가 `GET /api/v1/tenants/me` 를 호출한다
- **THEN** 시스템은 해당 사용자의 `tenant_id` 에 매칭되는 테넌트 정보를 반환한다 (`{id, name, plan, api_quota_monthly, created_at}`)

#### Scenario: 다른 테넌트 정보 접근 시도
- **WHEN** 사용자가 `GET /api/v1/tenants/{other_tenant_id}` 를 호출한다
- **THEN** 시스템은 HTTP 404 `{detail: "tenant_not_found", code: "NOT_FOUND"}` 를 반환한다 (자기 테넌트 외 조회 불가)

### Requirement: 소매점(Shop) 관리

시스템은 `shops(id, tenant_id, name, business_number, created_at, updated_at)` 테이블로 테넌트 소속 소매점을 관리해야 한다(MUST). `tenant_id` 는 `tenants.id` 외래키이며 `ON DELETE CASCADE` 다. 한 테넌트가 여러 매장을 운영할 수 있다.

#### Scenario: 소매점 등록
- **WHEN** 인증된 테넌트 오너가 `POST /api/v1/shops` 로 `{name: "강남점", business_number: "123-45-67890"}` 을 요청한다
- **THEN** 시스템은 요청자의 `tenant_id` 로 shop 레코드를 생성하고 HTTP 201 로 반환한다

#### Scenario: 소매점 목록 조회
- **WHEN** 인증된 사용자가 `GET /api/v1/shops` 를 호출한다
- **THEN** 시스템은 `WHERE tenant_id = :current_tenant_id` 필터가 강제된 쿼리로 해당 테넌트 소속 매장 목록만 반환한다

#### Scenario: 다른 테넌트 소매점 접근
- **WHEN** 테넌트 A 의 사용자가 테넌트 B 소속 `shop_id` 로 `GET /api/v1/shops/{id}` 를 호출한다
- **THEN** 시스템은 HTTP 404 를 반환한다 (존재하지만 격리로 숨김)

### Requirement: 사용자 엔티티 및 테넌트 소속

시스템은 `users(id, tenant_id, email, auth_provider, provider_user_id, role, password_hash, last_login_at, created_at, updated_at)` 테이블로 사용자를 관리해야 한다(MUST). `(auth_provider, provider_user_id)` 는 UNIQUE 제약을 가지며, `role` 은 `owner`/`staff` 이고 기본값은 `owner`, `auth_provider` 는 `kakao`/`naver`/`local` 이다.

#### Scenario: 사용자 최초 생성
- **WHEN** OAuth 로그인 후 해당 프로바이더 사용자가 최초 접근한다
- **THEN** 시스템은 `tenants` 를 자동 생성하고 `users` 를 `role='owner'`, `auth_provider=<provider>`, `provider_user_id=<id>` 로 1건 생성한다

#### Scenario: 재로그인
- **WHEN** 기존 사용자가 동일 프로바이더로 재로그인한다
- **THEN** 시스템은 `(auth_provider, provider_user_id)` 로 기존 사용자를 찾아 `last_login_at` 만 갱신하고 JWT 를 발급한다

### Requirement: 테넌트 격리 의존성 (Row-Level Filter)

시스템은 FastAPI 의존성 `get_current_tenant` 와 `get_current_user` 를 제공해야 한다(MUST). 모든 도메인 라우트는 이 의존성을 통해 현재 테넌트 id 를 획득하고, 서비스 레이어의 모든 쿼리에 `WHERE tenant_id = :current_tenant_id` 를 강제한다.

#### Scenario: 인증되지 않은 요청
- **WHEN** 클라이언트가 `Authorization` 헤더 없이 `GET /api/v1/shops` 를 호출한다
- **THEN** 시스템은 HTTP 401 `{detail: "missing_bearer", code: "UNAUTHORIZED"}` 를 반환한다

#### Scenario: 위조된 JWT 토큰
- **WHEN** 서명이 검증되지 않는 `Authorization: Bearer <invalid_jwt>` 헤더로 요청한다
- **THEN** 시스템은 HTTP 401 `{detail: "invalid_token", code: "UNAUTHORIZED"}` 를 반환한다

#### Scenario: 만료된 access token
- **WHEN** 만료 시각이 지난 access token 으로 요청한다
- **THEN** 시스템은 HTTP 401 `{detail: "token_expired", code: "UNAUTHORIZED"}` 를 반환한다 (클라이언트는 refresh flow 로 갱신해야 함)

#### Scenario: 존재하지 않는 사용자
- **WHEN** JWT 서명은 유효하나 `sub` 에 해당하는 사용자가 DB 에 없다
- **THEN** 시스템은 HTTP 401 `{detail: "user_not_found", code: "UNAUTHORIZED"}` 를 반환한다

### Requirement: 테넌트 월간 API 쿼터

시스템은 테넌트별 월간 API 쿼터를 Redis 카운터로 관리해야 한다(SHALL). 키는 `quota:tenant:{tenant_id}:{YYYYMM}` 형식이며, `INCR` 호출 후 해당 월 최초 호출 시 `EXPIREAT` 으로 다음달 1일 00:00 KST 까지 TTL 을 설정한다.

#### Scenario: 쿼터 정상 소비
- **WHEN** 테넌트의 이번달 호출 카운터가 `api_quota_monthly` 미만이다
- **THEN** 시스템은 카운터를 증가시키고 응답 헤더에 `X-Tenant-Quota-Remaining` 을 포함한다

#### Scenario: 쿼터 초과
- **WHEN** 테넌트의 이번달 호출 카운터가 `api_quota_monthly` 에 도달했다
- **THEN** 시스템은 HTTP 429 `{detail: "tenant_quota_exceeded", code: "QUOTA_EXCEEDED"}` 를 반환하고 요청을 처리하지 않는다

#### Scenario: 월 경계 리셋
- **WHEN** UTC+9 기준 매월 1일 00:00 이 지나간다
- **THEN** 기존 `quota:tenant:{tenant_id}:{이전월}` 키는 TTL 만료로 삭제되고, 신규 월 키로 0 부터 카운트된다

### Requirement: 크로스 테넌트 데이터 유출 방지 검증

시스템은 모든 `tenant_id` 격리 테이블(`shops`, `users`, `procurement_orders`, `procurement_results`, `listings`)에 대해 테넌트 A 의 토큰으로 테넌트 B 의 레코드에 접근하려 할 때 HTTP 404 를 반환해야 한다(MUST). 격리 실패는 보안 사고로 분류한다.

#### Scenario: 타 테넌트 주문 조회 시도
- **WHEN** 테넌트 A 의 사용자가 테넌트 B 가 생성한 `procurement_order_id` 로 `GET /api/v1/procurement/orders/{id}` 를 호출한다
- **THEN** 시스템은 HTTP 404 `{detail: "order_not_found", code: "NOT_FOUND"}` 를 반환한다 (테넌트 B 소속임을 노출하지 않음)

#### Scenario: 타 테넌트 shop_id 로 주문 생성 시도
- **WHEN** 테넌트 A 의 사용자가 테넌트 B 소속 `shop_id` 를 지정해 `POST /api/v1/procurement/orders` 를 요청한다
- **THEN** 시스템은 HTTP 404 `{detail: "shop_not_found", code: "NOT_FOUND"}` 를 반환하며 주문을 생성하지 않는다
