## MODIFIED Requirements

### Requirement: 검색 엔드포인트

시스템은 `GET /api/v1/search?q=<keyword>&limit=<n>` 엔드포인트를 유지해야 한다(MUST). 입력은 Pydantic `SearchRequest` 로 검증하고 응답은 Pydantic `SearchResponse` 로 직렬화한다. **피벗 후 본 엔드포인트는 백엔드 크롤링을 수행하지 않으며, 대신 현재 테넌트의 업로드된 `procurement_results` 중 `product_data.raw_title` 또는 옵션 텍스트에 `q` 가 포함된 항목들을 랭킹·정렬해 반환한다.** 모든 호출은 `Depends(get_current_tenant)` 를 통해 인증된 테넌트에 격리된다.

#### Scenario: 정상 요청 (업로드 결과 기반)
- **WHEN** 인증된 테넌트가 `GET /api/v1/search?q=코카콜라&limit=20` 을 호출하고 해당 테넌트의 `procurement_results` 에 매칭 항목이 10건 존재한다
- **THEN** 시스템은 HTTP 200 으로 `{results: [...개당 실가 오름차순 정렬된 10개 결과...], sources: {naver: "ok", coupang: "ok"}, tenant_id: <id>, cached: false}` 를 반환한다

#### Scenario: 매칭 결과가 없음
- **WHEN** 테넌트의 업로드 결과에 `q` 매칭 항목이 없다
- **THEN** 시스템은 HTTP 200 으로 `{results: [], sources: {}, tenant_id: <id>, cached: false, hint: "no_uploaded_results"}` 를 반환한다 (빈 배열 + 힌트)

#### Scenario: 입력 검증 실패
- **WHEN** `q` 가 빈 문자열이거나 `limit` 이 1–100 범위 밖이다
- **THEN** HTTP 422 + `{detail: <pydantic 에러>, code: "INVALID_REQUEST"}` 를 반환한다

#### Scenario: 인증 누락
- **WHEN** `Authorization` 헤더 없이 `GET /api/v1/search` 를 호출한다
- **THEN** HTTP 401 + `{detail: "missing_bearer", code: "UNAUTHORIZED"}` 를 반환한다

### Requirement: 응답 캐시

동일 테넌트·동일 검색어·limit 조합에 대해 시스템은 Redis cache-aside 전략을 적용해야 한다(SHALL). 기본 TTL 은 10분이며, `SEARCH_CACHE_TTL_SECONDS` 환경변수로 조정 가능하다. 캐시 키는 **`"search:" + tenant_id + ":" + md5(normalized_query + "|" + limit)`** 형식으로 테넌트 격리를 보장한다.

#### Scenario: 캐시 히트 즉시 반환
- **WHEN** 동일 테넌트의 직전 10분 이내 같은 쿼리가 이미 처리되어 캐시되었다
- **THEN** 시스템은 외부 호출 없이 캐시된 응답을 200ms 이내에 반환하고 `cached: true` 메타를 부여한다

#### Scenario: 다른 테넌트 동일 쿼리
- **WHEN** 테넌트 A 가 `q=코카콜라` 를 캐시한 상태에서 테넌트 B 가 동일 쿼리를 요청한다
- **THEN** 캐시 키가 `tenant_id` 네임스페이스로 분리되어 있어 테넌트 B 는 캐시 히트 없이 자기 데이터로 새 응답을 생성한다 (크로스 테넌트 격리 유지)

#### Scenario: 캐시 강제 갱신
- **WHEN** 요청에 `force_refresh=true` 쿼리 파라미터가 포함된다
- **THEN** 시스템은 캐시를 무시하고 DB 에서 다시 집계하며 결과를 캐시에 덮어쓴다

### Requirement: 일일 쿼터 관리

~~시스템은 Redis 기반 일일 쿼터 카운터를 유지해야 한다(SHALL). 네이버 쇼핑 API 는 `INCR naver:quota:<YYYYMMDD>` + `EXPIREAT <익일 00:00 KST>` 로 카운트하며, 응답에는 `quota_remaining` 메타를 포함한다.~~

**재정의**: 본 요구사항은 **테넌트 월간 API 쿼터**로 완전 대체된다. 네이버 플랫폼별 일일 쿼터는 피벗 후 의미가 없다(백엔드가 네이버 API 를 호출하지 않음). 상세는 `tenancy` 스펙의 "테넌트 월간 API 쿼터" Requirement 로 이관되었다.

#### Scenario: 테넌트 쿼터 정상 범위
- **WHEN** 현재 테넌트의 이번달 호출이 `tenants.api_quota_monthly` 미만이다
- **THEN** 카운터를 증가시키고 응답 헤더에 `X-Tenant-Quota-Remaining: <남은 수치>` 를 포함한다

#### Scenario: 테넌트 쿼터 소진
- **WHEN** 테넌트의 이번달 호출이 `api_quota_monthly` 에 도달했다
- **THEN** HTTP 429 + `{detail: "tenant_quota_exceeded", code: "QUOTA_EXCEEDED"}` 를 반환한다

### Requirement: 에러 응답 표준화

시스템의 모든 에러 응답은 `{detail: str, code: str}` 구조를 따라야 한다(MUST). 상세 에러는 structlog 로 `correlation_id` + `tenant_id` 와 함께 기록하고 Sentry 에 전달한다. **피벗 후 `tenant_id` 가 기록 필드로 추가** 된다.

#### Scenario: 업스트림 타임아웃 (업로드 처리 지연)
- **WHEN** 대량 배치 업로드 처리가 타임아웃된다
- **THEN** 응답은 HTTP 504 + `{detail: "upstream_timeout", code: "UPSTREAM_TIMEOUT"}` 이고, 로그에 `correlation_id` + `tenant_id` 가 포함된다

#### Scenario: 내부 서버 에러
- **WHEN** 예상치 못한 예외가 발생한다
- **THEN** 응답은 HTTP 500 + `{detail: "internal_error", code: "INTERNAL"}` 이며 내부 상세는 로그에만 기록된다 (클라이언트 노출 없음)

### Requirement: 관측성

모든 요청에는 `correlation_id` 와 `tenant_id` 가 미들웨어에서 생성·주입되어야 한다(MUST). **피벗 후 `tenant_id` 컨텍스트가 structlog 에 추가된다.** 프로메테우스 메트릭은 다음으로 재정의된다:

- `search_requests_total{tenant_id, status}` — 테넌트별 요청 수
- `search_cache_hit_total{tenant_id}` — 테넌트별 캐시 히트 수
- `llm_fallback_total{tenant_id}` — 테넌트별 LLM 폴백 발생 수
- `tenant_quota_remaining{tenant_id}` — 테넌트 월간 쿼터 잔량

**제거된 메트릭**: `platform_quota_remaining` (네이버 일일 쿼터) — 플랫폼 기반 쿼터가 피벗 대상이므로 삭제.

#### Scenario: correlation_id + tenant_id 전파
- **WHEN** 요청을 처리하는 동안 여러 로그 이벤트가 발생한다
- **THEN** 해당 요청의 모든 로그에 동일 `correlation_id` 와 `tenant_id` 가 포함된다

#### Scenario: 메트릭 노출
- **WHEN** `/metrics` 엔드포인트가 호출된다
- **THEN** 프로메테우스 포맷으로 모든 커스텀 메트릭이 `tenant_id` 라벨과 함께 노출된다

### Requirement: 상태 점검

시스템은 `/health/live` 와 `/health/ready` 엔드포인트를 인증 없이 제공해야 한다(SHALL). `live` 는 프로세스 생존만, `ready` 는 Postgres·Redis 연결을 확인한다. 이 요구사항은 피벗 전과 동일하나 **인증 면제 라우트 목록에 명시** 된다.

#### Scenario: live (인증 불필요)
- **WHEN** 인증 헤더 없이 `/health/live` 가 호출된다
- **THEN** 프로세스가 살아있으면 HTTP 200 + `{status: "alive"}` 를 반환한다

#### Scenario: ready 실패
- **WHEN** Postgres 연결이 끊긴 상태에서 `/health/ready` 가 호출된다
- **THEN** HTTP 503 + `{status: "not_ready", detail: "postgres:<err>"}` 를 반환한다
