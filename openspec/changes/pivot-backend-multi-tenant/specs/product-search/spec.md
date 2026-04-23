## REMOVED Requirements

### Requirement: 네이버 쇼핑 검색 결과 수집

**Reason**: 백엔드가 직접 네이버 쇼핑 API 를 호출하는 구조는 피벗 대상 — 클라이언트(Tauri/확장)가 사용자 세션에서 DOM 파싱 결과를 업로드하는 구조로 전환됨. 관련 코드 `backend/app/collectors/naver.py` 삭제.

**Migration**: 기존 네이버 검색 결과 테이블은 `procurement_results(platform='naver', product_data=...)` 로 대체된다. 친구용 데이터는 마이그레이션하지 않고 폐기.

### Requirement: 쿠팡 검색 결과 수집

**Reason**: 쿠팡 Akamai 차단·법적 리스크로 서버측 크롤링 폐기. 관련 코드 `backend/app/collectors/coupang.py` 삭제.

**Migration**: 클라이언트 업로드(`procurement_results(platform='coupang', product_data=...)`)로 대체.

### Requirement: 수집 호출 Rate 제한 및 UA 로테이션

**Reason**: 백엔드 크롤링이 제거되어 Rate/UA 로테이션 로직 자체가 불필요. 관련 코드 `backend/app/collectors/rate_limiter.py`, `http_client.py` 삭제.

**Migration**: 테넌트 월간 쿼터(`quota_service.py` 재설계분)가 남용 방지 역할을 대체한다. 클라이언트 측 Rate 는 각 클라이언트 책임.

## MODIFIED Requirements

### Requirement: 플랫폼 병렬 호출과 partial failure

시스템은 클라이언트가 업로드한 여러 플랫폼(`naver`, `coupang`, 기타)의 결과를 단일 주문에 대해 병렬 조회·집계할 수 있어야 한다(MUST). 플랫폼별 결과 유무에 따라 응답 `sources` 메타에 상태를 명시한다.

#### Scenario: 두 플랫폼 결과가 모두 업로드되어 있다
- **WHEN** `procurement_orders.id=42` 에 `platform='naver'` 와 `platform='coupang'` 결과가 모두 존재한다
- **THEN** 응답은 두 플랫폼 결과를 모두 포함하고 `sources: {naver: "ok", coupang: "ok"}` 를 반환한다

#### Scenario: 한 플랫폼 결과만 있다
- **WHEN** `platform='naver'` 결과만 업로드되어 있다
- **THEN** 응답은 200 상태로 네이버 결과만 포함하고 `sources: {naver: "ok", coupang: "missing"}` 를 반환한다

#### Scenario: 업로드된 결과가 전혀 없다
- **WHEN** 주문은 존재하지만 `procurement_results` 가 0 건이다
- **THEN** 응답은 HTTP 200 + `{results: [], sources: {}, order_status: "pending"}` 를 반환한다 (클라이언트가 수집 진행중임을 의미)
