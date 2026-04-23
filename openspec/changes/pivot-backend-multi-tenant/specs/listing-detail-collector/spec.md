## REMOVED Requirements

### Requirement: 상세 페이지 옵션·가격·배송비 추출

**Reason**: 서버측 상세 페이지 수집 전체 폐기. 대법원 2017 잡코리아 판례·쿠팡 Akamai 차단으로 상용화 불가. 관련 코드 `backend/app/collectors/naver_detail.py`, `coupang_detail.py`, `remote_scraper.py` 전체 삭제.

**Migration**: 각 테넌트의 클라이언트(Tauri 데스크톱 앱·브라우저 확장)가 사용자 로그인 세션에서 DOM 을 직접 파싱해 백엔드에 업로드한다. 아래 "클라이언트 업로드 기반 상세 수신" 요구사항으로 대체.

### Requirement: 상세 페이지 응답 캐시

**Reason**: 백엔드 상세 수집이 없으므로 상세 응답 캐시(`services/detail_cache_service.py`)도 불필요.

**Migration**: 동일 상품을 여러 테넌트가 반복 수집해도 각 테넌트의 `procurement_results` 로 별도 저장된다 (테넌트 격리 원칙). 향후 공용 카탈로그 캐시 필요 시 별도 제안에서 재검토.

### Requirement: 헤드리스 렌더 폴백

**Reason**: Playwright 기반 서버 렌더 폴백 전체 폐기. `playwright` 의존성 제거.

**Migration**: 클라이언트가 각자의 로그인 세션에서 렌더된 DOM 에 접근하므로 헤드리스 렌더 자체가 불필요.

## ADDED Requirements

### Requirement: 클라이언트 업로드 기반 상세 수신

시스템은 클라이언트(Tauri·브라우저 확장)가 파싱한 상품 상세 데이터를 JSON 으로 수신해야 한다(MUST). 수신 스키마는 `{platform, raw_title, options: [{name, price, stock?}], shipping_fee?, shipping_confidence?, url, captured_at, ...}` 이며, 업로드 엔드포인트는 `procurement-results` 스펙에 정의된 `POST /api/v1/procurement/orders/{id}/results` 또는 `/results/batch` 를 재사용한다.

#### Scenario: 네이버 스마트스토어 상세 업로드
- **WHEN** 클라이언트가 `platform='naver'`, `url='https://smartstore.naver.com/{store}/products/{productId}'` 와 파싱된 옵션 리스트를 업로드한다
- **THEN** 시스템은 `procurement_results` 에 레코드를 저장하고, 후속 조회 시 해당 order 의 결과로 포함된다

#### Scenario: 쿠팡 상세 업로드
- **WHEN** 클라이언트가 `platform='coupang'`, `url='https://www.coupang.com/vp/products/{productId}'` 와 옵션 리스트를 업로드한다
- **THEN** 시스템은 정상 저장한다 (플랫폼 값 외 처리는 동일)

#### Scenario: 배송비 명시 여부 필드
- **WHEN** 클라이언트가 `shipping_fee: 3000, shipping_confidence: "explicit"` 를 전송한다
- **THEN** 시스템은 원본 값을 보존하며, `shipping_policy` 재계산은 `RECOMPUTE_SAVINGS_ON_UPLOAD=true` 일 때만 적용한다

### Requirement: 업로드 실패 시 그래이스풀 응답

시스템은 단일 업로드 실패가 다른 업로드나 주문 상태에 영향을 주지 않도록 보장해야 한다(SHALL).

#### Scenario: 배치 업로드 중 트랜잭션 롤백
- **WHEN** 10건 중 2건이 검증 실패다
- **THEN** 시스템은 트랜잭션을 롤백하고 HTTP 422 를 반환하며 원본 `procurement_results` 상태를 변경하지 않는다

#### Scenario: 단건 업로드 실패
- **WHEN** 단건 업로드가 422 로 실패한다
- **THEN** 해당 주문의 다른 기존 결과들은 그대로 유지되고, 주문 `status` 는 변하지 않는다
