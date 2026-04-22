## ADDED Requirements

### Requirement: 네이버 쇼핑 검색 결과 수집

시스템은 검색어(`query`)를 받아 네이버 쇼핑 검색 API(`https://openapi.naver.com/v1/search/shop.json`)를 호출하고 후보 상품 리스팅을 반환해야 한다(SHALL). 호출에는 `X-Naver-Client-Id`/`X-Naver-Client-Secret` 헤더와 `display`·`start`·`sort` 파라미터를 적용한다.

#### Scenario: 정상 검색어로 리스팅을 받는다
- **WHEN** 사용자가 `q="코카콜라"`, `limit=20`으로 검색을 요청한다
- **THEN** 시스템은 네이버 API에서 최대 20건의 상품 리스팅을 받아 `platform_product_id`, `raw_title`, `mall_name`, `product_url`, `lprice` 등을 포함한 중립 스키마로 반환한다

#### Scenario: 일일 쿼터가 초과되었다
- **WHEN** 네이버 API가 HTTP 429를 반환하거나 Redis 쿼터 카운터가 일일 25,000건에 도달한 상태다
- **THEN** 시스템은 네이버 호출을 스킵하고 응답 `sources.naver`에 `"quota_exceeded"`를 기록한 partial 결과를 반환한다

#### Scenario: 네트워크 장애로 호출이 실패한다
- **WHEN** 네이버 API 호출이 타임아웃·5xx로 실패한다
- **THEN** 시스템은 지수 백오프 + jitter로 최대 3회 재시도하고, 그래도 실패하면 `sources.naver`에 `"error:<code>"`를 기록한 partial 결과를 반환한다

### Requirement: 쿠팡 검색 결과 수집

시스템은 검색어를 받아 쿠팡 검색 페이지(`https://www.coupang.com/np/search?q=<keyword>`)를 저빈도로 fetch하고, HTML에서 후보 상품 리스팅을 추출해야 한다(SHALL). 쿠팡 Partners API는 본 MVP에서 사용하지 않는다.

#### Scenario: 정상 검색어로 리스팅을 받는다
- **WHEN** 사용자가 `q="코카콜라"`로 검색을 요청한다
- **THEN** 시스템은 쿠팡 검색 페이지를 fetch해 `productId`, `rawTitle`, `sellerId`, `productUrl`, `representativePrice` 등 후보 리스팅을 반환한다

#### Scenario: Akamai/봇 탐지로 차단되었다
- **WHEN** 쿠팡이 HTTP 403 또는 `Pardon Our Interruption` 페이지를 반환한다
- **THEN** 시스템은 서킷브레이커를 `open`으로 전환(60초)하고 응답 `sources.coupang`에 `"blocked"`를 기록한 partial 결과를 반환한다

### Requirement: 플랫폼 병렬 호출과 partial failure

시스템은 네이버와 쿠팡 수집기를 `asyncio.gather(..., return_exceptions=True)` 로 병렬 호출해야 한다(MUST). 한 플랫폼이 실패해도 다른 플랫폼의 결과는 반드시 반환되어야 한다.

#### Scenario: 두 플랫폼이 모두 성공한다
- **WHEN** 네이버·쿠팡 수집이 모두 성공한다
- **THEN** 응답은 두 플랫폼 리스팅을 모두 포함하고 `sources: {naver: "ok", coupang: "ok"}` 를 반환한다

#### Scenario: 한 플랫폼만 성공한다
- **WHEN** 네이버는 성공이고 쿠팡이 차단되었다
- **THEN** 응답은 200 상태로 네이버 결과만 포함하고 `sources: {naver: "ok", coupang: "blocked"}` 를 반환한다

#### Scenario: 두 플랫폼 모두 실패한다
- **WHEN** 네이버·쿠팡 수집이 모두 실패한다
- **THEN** 시스템은 HTTP 502 + `{detail: "all_sources_failed", code: "UPSTREAM_DOWN"}` 을 반환한다

### Requirement: 수집 호출 Rate 제한 및 UA 로테이션

시스템은 각 플랫폼별로 분당 요청 한도(`NAVER_RPM`, `COUPANG_RPM`)를 적용해야 한다(SHALL). 요청 간 랜덤 지연(0.5–2초 jitter)과 User-Agent 로테이션(데스크톱 UA 10개 풀)을 적용한다.

#### Scenario: 분당 한도를 초과한 요청
- **WHEN** 동일 플랫폼 호출이 분당 한도를 초과한다
- **THEN** 초과 호출은 한도 리셋 시점까지 대기 후 실행된다

#### Scenario: User-Agent 로테이션 적용
- **WHEN** 각 외부 요청을 발행한다
- **THEN** 요청 헤더의 `User-Agent`는 사전 정의된 10개 풀에서 랜덤 선택된 값을 사용한다
