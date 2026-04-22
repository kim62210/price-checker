## ADDED Requirements

### Requirement: 상세 페이지 옵션·가격·배송비 추출

시스템은 리스팅 식별자(플랫폼별 URL)로 상세 페이지를 fetch하고, **옵션별 가격·옵션명 텍스트·배송비**를 추출해 중립 스키마로 반환해야 한다(SHALL).

#### Scenario: 네이버 스마트스토어 SPA 상세
- **WHEN** 수집기가 `https://smartstore.naver.com/{store}/products/{productId}` URL을 처리한다
- **THEN** Playwright로 페이지를 렌더링하고 내부 상품 JSON 또는 DOM에서 옵션 리스트(`optionCombinations`·`optionSimple`)를 파싱해 `[{attrs, price, stock, option_name_text}]` 형태로 반환한다

#### Scenario: 쿠팡 상세 페이지(정적/Ajax)
- **WHEN** 수집기가 `https://www.coupang.com/vp/products/{productId}?vendorItemId=...` URL을 처리한다
- **THEN** 먼저 httpx + selectolax로 페이지 내 `exports.sdp` JSON 블록을 추출 시도하고, 실패 시 Playwright 폴백으로 `productId`/`itemId`/`vendorItemId`별 옵션을 파싱한다

#### Scenario: 배송비 정보가 명시되어 있다
- **WHEN** 상세 페이지에 "배송비 3,000원" 같은 명시적 배송비 문자열이 있다
- **THEN** 추출된 `shipping_fee: 3000` 과 `shipping_confidence: "explicit"` 을 반환한다

#### Scenario: 배송비가 명시되지 않거나 조건부다
- **WHEN** "5만원 이상 무료배송" 같은 조건부이거나 배송비 문자열이 없다
- **THEN** 기본 배송비 정책(쿠팡 로켓 비회원 3,000원·스마트스토어 셀러 기본 3,000원)을 적용하고 `shipping_confidence: "estimated"` 를 반환한다

### Requirement: 상세 페이지 응답 캐시

시스템은 상세 페이지 응답을 Redis에 캐시해 재수집을 줄여야 한다(SHALL). 기본 TTL은 6시간이며, 환경변수 `DETAIL_CACHE_TTL_SECONDS` 로 조정 가능하다.

#### Scenario: 캐시 히트
- **WHEN** 동일 URL이 TTL 내에 다시 요청된다
- **THEN** 외부 호출 없이 캐시된 결과를 반환한다

#### Scenario: 캐시 만료 후 재요청
- **WHEN** TTL이 만료된 후 동일 URL이 다시 요청된다
- **THEN** 외부에 재fetch하고 결과를 캐시에 덮어쓴다

#### Scenario: 캐시 우회 플래그
- **WHEN** `force_refresh: true` 파라미터가 전달된다
- **THEN** 캐시를 무시하고 재fetch하며 결과를 캐시에 갱신한다

### Requirement: 헤드리스 렌더 폴백

시스템은 정적 HTML 파싱 실패 또는 봇 차단 감지 시 Playwright로 폴백해야 한다(SHALL). 동시 실행은 `asyncio.Semaphore(PLAYWRIGHT_CONCURRENCY=2)` 로 제한한다.

#### Scenario: 정적 파싱 실패 시 폴백
- **WHEN** httpx + selectolax 파싱이 필수 필드(옵션/가격)를 추출하지 못한다
- **THEN** 동일 URL을 Playwright(stealth 옵션)로 렌더해 재파싱한다

#### Scenario: Playwright 동시성 제한
- **WHEN** 3개 이상의 상세 수집이 동시에 Playwright 폴백을 요청한다
- **THEN** 2개만 동시에 실행되고 나머지는 세마포어 대기열에 들어간다

### Requirement: 수집 실패 시 그래이스풀 응답

시스템은 특정 리스팅 상세 수집이 실패해도 해당 리스팅을 결과 목록에서 제외하거나 `detail_status: "error:<reason>"` 메타로 표시해야 한다(SHALL). 전체 파이프라인은 중단되지 않는다.

#### Scenario: 특정 리스팅 차단
- **WHEN** 10개 리스팅 중 2개가 403으로 차단된다
- **THEN** 나머지 8개 리스팅은 정상 처리되고, 실패한 2개는 `detail_status: "blocked"` 로 메타에 기록된다
