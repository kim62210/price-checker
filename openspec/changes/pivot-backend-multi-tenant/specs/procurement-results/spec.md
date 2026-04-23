## ADDED Requirements

### Requirement: 발주 결과 엔티티

시스템은 `procurement_results(id, order_id, tenant_id, platform, product_data, savings_krw, fetched_at, created_at)` 테이블로 클라이언트가 업로드한 수집 결과를 저장해야 한다(MUST). `platform` 은 `naver`/`coupang`/`11st` 등의 식별자, `product_data` 는 JSONB 로 `{raw_title, options: [...], shipping_fee, price, url, ...}` 구조를 담는다. `tenant_id` 는 조회 성능을 위한 비정규화로 order 의 tenant_id 와 동일해야 한다.

#### Scenario: 결과 단건 업로드
- **WHEN** 인증된 클라이언트(브라우저 확장·Tauri 앱)가 `POST /api/v1/procurement/orders/{order_id}/results` 로 `{platform: "coupang", product_data: {raw_title: "코카콜라 500ml 30개", options: [{name: "30개입", price: 25000}], shipping_fee: 0, url: "https://..."}}` 를 업로드한다
- **THEN** 시스템은 `order_id` 가 요청자의 테넌트 소속인지 검증한 후, `tenant_id` 를 order 로부터 복사해 레코드를 생성하고 HTTP 201 + `{id, order_id, tenant_id, platform, fetched_at}` 을 반환한다

#### Scenario: 다른 테넌트 주문에 업로드 시도
- **WHEN** 테넌트 A 의 클라이언트가 테넌트 B 소속 `order_id` 로 결과를 업로드한다
- **THEN** 시스템은 HTTP 404 `{detail: "order_not_found", code: "NOT_FOUND"}` 를 반환한다

#### Scenario: 필수 필드 누락
- **WHEN** `platform` 또는 `product_data.raw_title` 이 누락된 요청이 온다
- **THEN** 시스템은 HTTP 422 `{detail: <pydantic 에러>, code: "INVALID_REQUEST"}` 를 반환한다

### Requirement: 결과 일괄 업로드

시스템은 `POST /api/v1/procurement/orders/{order_id}/results/batch` 엔드포인트로 다건 업로드를 지원해야 한다(SHALL). 요청 본문은 `{items: [{platform, product_data, savings_krw?}, ...]}` 이며 최대 100건, 트랜잭션 단위 처리.

#### Scenario: 정상 일괄 업로드
- **WHEN** 클라이언트가 10건의 결과를 `POST /results/batch` 로 업로드한다
- **THEN** 시스템은 모든 레코드를 단일 트랜잭션으로 INSERT 하고 HTTP 201 + `{inserted: 10, result_ids: [...]}` 을 반환한다

#### Scenario: 일부 레코드 검증 실패
- **WHEN** 10건 중 2건이 `product_data.raw_title` 누락이다
- **THEN** 시스템은 트랜잭션을 롤백하고 HTTP 422 를 반환한다 (전체 실패, 부분 저장 금지)

#### Scenario: 최대 건수 초과
- **WHEN** 101건 이상을 배치로 전송한다
- **THEN** 시스템은 HTTP 413 `{detail: "batch_too_large", code: "PAYLOAD_TOO_LARGE"}` 를 반환한다

### Requirement: 결과 목록 조회

시스템은 `GET /api/v1/procurement/orders/{order_id}/results?platform=<p>&limit=<n>&offset=<m>` 엔드포인트를 제공해야 한다(MUST). 응답은 해당 order 의 결과만 포함하며 `fetched_at DESC` 정렬.

#### Scenario: 전체 결과 조회
- **WHEN** 인증된 사용자가 자신의 테넌트 소속 `order_id` 로 결과를 조회한다
- **THEN** 시스템은 HTTP 200 + `{items: [{id, platform, product_data, savings_krw, fetched_at}, ...], total}` 을 반환한다

#### Scenario: 플랫폼 필터
- **WHEN** `?platform=coupang` 파라미터를 지정한다
- **THEN** 시스템은 쿠팡 수집 결과만 반환한다

### Requirement: 집계 리포트

시스템은 `GET /api/v1/procurement/reports/summary?shop_id=<id>&from=<YYYY-MM-DD>&to=<YYYY-MM-DD>` 엔드포인트를 제공해야 한다(SHALL). 응답은 기간 내 테넌트 소속 주문의 플랫폼별 수집 건수·총 절감액·평균 응답 시간을 포함한다.

#### Scenario: 정상 리포트
- **WHEN** 인증된 사용자가 `GET /reports/summary?from=2026-04-01&to=2026-04-30` 을 호출한다
- **THEN** 시스템은 HTTP 200 + `{orders: 45, results: 312, total_savings_krw: 1250000, by_platform: {coupang: {results: 180, savings: 800000}, naver: {results: 132, savings: 450000}}}` 을 반환한다

#### Scenario: 기간 파라미터 누락
- **WHEN** `from` 또는 `to` 가 없다
- **THEN** 시스템은 기본값으로 "지난 30일" 을 적용한다

### Requirement: 업로드 시 테넌트 격리 강제

시스템은 결과 업로드 시 서버가 `order_id` 로부터 `tenant_id` 를 자동 복사해야 한다(MUST). 클라이언트가 body 에 `tenant_id` 를 보내더라도 서버는 이를 무시하고 order 의 tenant_id 를 사용한다.

#### Scenario: 클라이언트가 임의 tenant_id 전송
- **WHEN** 요청 body 에 `tenant_id: 999` 가 포함되어도 order 의 실제 tenant_id 는 42 다
- **THEN** 시스템은 `tenant_id: 42` 로 레코드를 저장한다 (스푸핑 차단)

### Requirement: `savings_krw` 계산 일관성

시스템은 `savings_krw` 를 클라이언트가 전송한 값 그대로 저장하거나 서버에서 `shipping_policy` + `ranking_service` 로 재계산해 덮어써야 한다(SHALL). 재계산 여부는 `RECOMPUTE_SAVINGS_ON_UPLOAD` 환경변수로 제어한다.

#### Scenario: 클라이언트 값 신뢰
- **WHEN** `RECOMPUTE_SAVINGS_ON_UPLOAD=false` 이며 클라이언트가 `savings_krw: 5000` 을 전송한다
- **THEN** 시스템은 그 값을 그대로 저장한다

#### Scenario: 서버 재계산
- **WHEN** `RECOMPUTE_SAVINGS_ON_UPLOAD=true` 이다
- **THEN** 시스템은 `product_data` 를 파서·배송비 서비스로 돌려 `savings_krw` 를 재계산하고 클라이언트 값 대신 저장한다
