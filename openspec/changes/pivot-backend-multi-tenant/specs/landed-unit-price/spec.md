## MODIFIED Requirements

### Requirement: 개당 실가 계산 공식

시스템은 옵션가(`price`)·배송비(`shipping_fee`)·파싱된 실 수량(`unit_quantity`)을 받아 `unit_price = (price + shipping_fee) / unit_quantity` 로 개당 실가를 계산해야 한다(MUST). 입력 소스는 크롤러 파싱 결과가 아니라 **`procurement_results.product_data` 로부터 추출된 값** 이며, 기준단위 환산 로직은 동일하게 Google Merchant 스키마를 준용한다. 계산 로직 자체는 피벗 전과 동일하다.

#### Scenario: 업로드된 결과 기반 계산
- **WHEN** `procurement_results.product_data = {price: 10000, shipping_fee: 3000, options: [{name: "12개입", ...}]}` 이며 파싱 결과 `unit_quantity=12, unit="ct"` 이다
- **THEN** 시스템은 `unit_price≈1083.33` 을 반환하고 표시값은 `원/개` 형식이다

#### Scenario: g 단위 환산 (회귀 보장)
- **WHEN** 업로드 결과에서 `price=9900, shipping_fee=0, unit_quantity=500, unit="g"` 가 추출된다
- **THEN** `unit_price=19.8 (원/g)` 이며 표시값은 `1,980원/100g` 형식으로 환산된다

#### Scenario: 수량 파싱 실패
- **WHEN** `unit_quantity` 가 `null` 또는 `0` 이다
- **THEN** `unit_price: null` 과 `unit_price_confidence: "low"` 를 반환한다 (0 나눗셈 방지)

### Requirement: 무료배송 조건 반영

시스템은 플랫폼별 배송비 정책을 적용해 개당 실가 계산에 반영해야 한다(SHALL). 쿠팡 로켓 비회원 19,800원 임계치·스마트스토어 `free_threshold` 로직은 피벗 전과 동일하다. 단 **입력 `shipping_fee` 는 클라이언트 업로드 값을 우선**하며, `shipping_confidence` 가 `explicit` 이면 서버 정책 재적용을 건너뛴다.

#### Scenario: 클라이언트가 명시적 배송비 업로드
- **WHEN** `product_data.shipping_fee=2500, shipping_confidence="explicit"` 이다
- **THEN** 서버는 2500원을 그대로 사용하고 `shipping_policy` 추정을 적용하지 않는다

#### Scenario: 배송비 누락 시 정책 적용
- **WHEN** `shipping_fee` 가 없거나 `shipping_confidence="estimated"` 이다
- **THEN** 서버는 `shipping_policy.py` 기본 규칙(쿠팡 로켓 3,000원 또는 19,800원 이상 무료 등)을 적용하고 `shipping_confidence="estimated"` 로 표기한다

#### Scenario: 스마트스토어 무료배송 임계치 초과
- **WHEN** 스마트스토어 셀러의 `free_threshold=30000`, 옵션가 35,000원이며 클라이언트 업로드 값에서 배송비가 명시되지 않았다
- **THEN** 서버는 `shipping_fee=0` 을 적용해 계산한다

### Requirement: 결과 정렬

시스템은 동일 주문(`procurement_orders.id`) 내 모든 `procurement_results` 의 옵션을 `unit_price` 오름차순으로 정렬해야 한다(MUST). `unit_price` 가 `null` 인 항목은 정렬 끝으로 밀어낸다. 서로 다른 주문·서로 다른 테넌트 간 정렬 비교는 수행하지 않는다(테넌트 격리).

#### Scenario: 단일 주문 내 혼합 결과 정렬
- **WHEN** 하나의 주문에 unit_price 가 `[1200, null, 900, 1500, null, 800]` 인 6개 옵션(다양한 `procurement_results` 에 분산)이 있다
- **THEN** 정렬된 결과는 `[800, 900, 1200, 1500, null, null]` 순서다

#### Scenario: 테넌트 격리 하에 정렬
- **WHEN** 응답 목록을 조회할 때 서비스는 `WHERE tenant_id = :current_tenant_id` 필터를 적용한 후 정렬한다
- **THEN** 다른 테넌트의 결과는 정렬 대상에서 제외된다

### Requirement: 단위 환산 일관성

시스템은 동일 주문 결과 내에서 가능하면 동일 기준단위로 정렬해야 한다(SHOULD). 단위가 섞이면(`g` 와 `ct` 등) 결과 응답에 `comparable_group` 플래그로 비교 가능성 그룹을 명시해야 한다(SHALL). 이 요구사항은 피벗 전과 동일하다.

#### Scenario: 단위 혼재
- **WHEN** 한 주문에 `g` 기준과 `ct` 기준 옵션이 섞여 있다
- **THEN** 응답은 `comparable_group: "by_weight" | "by_count"` 로 구분하고, 같은 그룹 내에서만 unit_price 정렬을 신뢰 가능한 것으로 표시한다
