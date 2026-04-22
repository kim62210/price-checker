## ADDED Requirements

### Requirement: 검색 엔드포인트

시스템은 `GET /api/v1/search?q=<keyword>&limit=<n>` 엔드포인트를 제공해야 한다(MUST). 입력은 Pydantic `SearchRequest` 로 검증하고 응답은 Pydantic `SearchResponse` 로 직렬화한다.

#### Scenario: 정상 요청
- **WHEN** 클라이언트가 `GET /api/v1/search?q=코카콜라&limit=20` 를 호출한다
- **THEN** 시스템은 HTTP 200 으로 `{results: [ ...개당 실가 오름차순 정렬된 옵션 목록... ], sources: {naver: "ok", coupang: "ok"}, cached: false}` 를 반환한다

#### Scenario: 입력 검증 실패
- **WHEN** `q` 가 빈 문자열이거나 `limit` 이 1–100 범위 밖이다
- **THEN** HTTP 422 + `{detail: <pydantic 에러>, code: "INVALID_REQUEST"}` 를 반환한다

#### Scenario: 모든 업스트림 실패
- **WHEN** 네이버·쿠팡 수집이 모두 실패한다
- **THEN** HTTP 502 + `{detail: "all_sources_failed", code: "UPSTREAM_DOWN"}` 를 반환한다

### Requirement: 응답 캐시

동일 검색어·limit 조합에 대해 시스템은 Redis cache-aside 전략을 적용해야 한다(SHALL). 기본 TTL 은 10분이며, `SEARCH_CACHE_TTL_SECONDS` 환경변수로 조정 가능하다. 캐시 키는 `"search:" + md5(normalized_query + "|" + limit)` 형식이다.

#### Scenario: 캐시 히트 즉시 반환
- **WHEN** 직전 10분 이내 같은 쿼리가 이미 처리되어 캐시되었다
- **THEN** 시스템은 외부 호출 없이 캐시된 응답을 200ms 이내에 반환하고 `cached: true` 메타를 부여한다

#### Scenario: 캐시 강제 갱신
- **WHEN** 요청에 `force_refresh=true` 쿼리 파라미터가 포함된다
- **THEN** 시스템은 캐시를 무시하고 외부를 다시 수집하며 결과를 캐시에 덮어쓴다

### Requirement: 일일 쿼터 관리

시스템은 Redis 기반 일일 쿼터 카운터를 유지해야 한다(SHALL). 네이버 쇼핑 API 는 `INCR naver:quota:<YYYYMMDD>` + `EXPIREAT <익일 00:00 KST>` 로 카운트하며, 응답에는 `quota_remaining` 메타를 포함한다.

#### Scenario: 쿼터 정상 범위
- **WHEN** 네이버 호출이 당일 24,000회 미만이다
- **THEN** 카운터를 증가시키고 정상 수집을 계속한다

#### Scenario: 쿼터 소진
- **WHEN** 네이버 호출 카운터가 25,000회에 도달했다
- **THEN** 네이버 수집은 스킵되고 `sources.naver: "quota_exceeded"` 로 메타가 표기되며 쿠팡 결과만 반환된다

### Requirement: 에러 응답 표준화

시스템의 모든 에러 응답은 `{detail: str, code: str}` 구조를 따라야 한다(MUST). 상세 에러는 structlog 로 correlation_id 와 함께 기록하고 Sentry 에 전달한다.

#### Scenario: 업스트림 타임아웃
- **WHEN** 수집 계층이 tenacity 재시도 후에도 타임아웃으로 실패한다
- **THEN** 응답은 HTTP 504 + `{detail: "upstream_timeout", code: "UPSTREAM_TIMEOUT"}` 이고, Sentry 에 correlation_id 포함한 에러가 전송된다

#### Scenario: 내부 서버 에러
- **WHEN** 예상치 못한 예외가 발생한다
- **THEN** 응답은 HTTP 500 + `{detail: "internal_error", code: "INTERNAL"}` 이며 내부 상세는 로그에만 기록된다(클라이언트 노출 없음)

### Requirement: 관측성

모든 요청에는 correlation_id 가 미들웨어에서 생성·주입되어야 한다(MUST). 프로메테우스 메트릭 `search_requests_total`·`search_cache_hit_total`·`llm_fallback_total`·`platform_quota_remaining` 을 제공한다.

#### Scenario: correlation_id 전파
- **WHEN** 요청을 처리하는 동안 여러 로그 이벤트가 발생한다
- **THEN** 해당 요청의 모든 로그에 동일 correlation_id 가 포함된다

#### Scenario: 메트릭 노출
- **WHEN** `/metrics` 엔드포인트가 호출된다
- **THEN** 프로메테우스 포맷으로 모든 커스텀 메트릭이 노출된다

### Requirement: 상태 점검

시스템은 `/health/live` 와 `/health/ready` 엔드포인트를 제공해야 한다(SHALL). `live` 는 프로세스 생존만, `ready` 는 Postgres·Redis 연결을 확인한다.

#### Scenario: live
- **WHEN** `/health/live` 가 호출된다
- **THEN** 프로세스가 살아있으면 HTTP 200 + `{status: "alive"}` 를 반환한다

#### Scenario: ready 실패
- **WHEN** Postgres 연결이 끊긴 상태에서 `/health/ready` 가 호출된다
- **THEN** HTTP 503 + `{status: "not_ready", detail: "postgres:<err>"}` 를 반환한다
