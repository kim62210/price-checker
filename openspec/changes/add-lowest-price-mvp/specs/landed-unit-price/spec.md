## ADDED Requirements

### Requirement: 개당 실가 계산 공식

시스템은 옵션가(`price`)·배송비(`shipping_fee`)·파싱된 실 수량(`unit_quantity`)을 받아 `unit_price = (price + shipping_fee) / unit_quantity` 로 개당 실가를 계산해야 한다(MUST). 기준단위는 Google Merchant 스키마(`g`, `ml`, `ct`, `sheet` 등)를 준용하고, 표시용으로는 `100g`·`100ml`·`1ct` 등 가독 단위로 환산한다.

#### Scenario: 정상 계산
- **WHEN** `price=10000, shipping_fee=3000, unit_quantity=12, unit="ct"` 가 주어진다
- **THEN** `unit_price≈1083.33` 을 반환하고 표시값은 `원/개` 형식이다

#### Scenario: g 단위 환산
- **WHEN** `price=9900, shipping_fee=0, unit_quantity=500, unit="g"` 가 주어진다
- **THEN** `unit_price=19.8 (원/g)` 이며 표시값은 `1,980원/100g` 형식으로 환산된다

#### Scenario: 수량 파싱 실패
- **WHEN** `unit_quantity` 가 `null` 또는 `0` 이다
- **THEN** `unit_price: null` 과 `unit_price_confidence: "low"` 를 반환한다 (0 나눗셈 방지)

### Requirement: 무료배송 조건 반영

시스템은 플랫폼별 배송비 정책을 적용해 개당 실가 계산에 반영해야 한다(SHALL). 쿠팡 로켓 비회원은 실결제액 19,800원 이상일 때 배송비 0, 스마트스토어 셀러는 `free_threshold` 이상일 때 배송비 0으로 간주한다. 와우 멤버십은 본 MVP 범위 외(사용자가 직접 최종 페이지에서 확인).

#### Scenario: 쿠팡 로켓 19,800원 미만
- **WHEN** 쿠팡 로켓 상품 `price=15000, shipping_fee는 미명시` 다
- **THEN** 시스템은 `shipping_fee=3000` 을 적용해 `unit_price` 를 계산하고 `shipping_confidence: "estimated"` 를 표기한다

#### Scenario: 쿠팡 로켓 19,800원 이상
- **WHEN** 쿠팡 로켓 상품 `price=25000` 이고 수량 1개다
- **THEN** 시스템은 `shipping_fee=0` 을 적용해 `unit_price` 를 계산한다

#### Scenario: 스마트스토어 무료배송 임계치 초과
- **WHEN** 스마트스토어 셀러의 `free_threshold=30000`, 옵션가 35,000원이다
- **THEN** `shipping_fee=0` 으로 계산한다

### Requirement: 결과 정렬

시스템은 동일 검색 결과 내 모든 옵션을 `unit_price` 오름차순으로 정렬해야 한다(MUST). `unit_price` 가 `null` 인 항목은 정렬 끝으로 밀어낸다.

#### Scenario: 혼합 결과 정렬
- **WHEN** 결과에 unit_price가 `[1200, null, 900, 1500, null, 800]` 인 6개 항목이 있다
- **THEN** 정렬된 결과는 `[800, 900, 1200, 1500, null, null]` 순서다

### Requirement: 단위 환산 일관성

시스템은 동일 검색 결과 내에서 가능하면 동일 기준단위로 정렬해야 한다(SHOULD). 단위가 섞이면(`g` 와 `ct` 등) 결과 응답에 `comparable_group` 플래그로 비교 가능성 그룹을 명시해야 한다(SHALL).

#### Scenario: 단위 혼재
- **WHEN** 결과에 `g` 기준과 `ct` 기준 옵션이 섞여 있다
- **THEN** 응답은 `comparable_group: "by_weight" | "by_count"` 로 구분하고, 같은 그룹 내에서만 unit_price 정렬을 신뢰 가능한 것으로 표시한다
