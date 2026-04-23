## ADDED Requirements

### Requirement: 발주 주문 엔티티

시스템은 `procurement_orders(id, shop_id, tenant_id, items, status, created_at, updated_at)` 테이블로 발주 주문을 관리해야 한다(MUST). `items` 는 JSONB 로 `[{sku, keyword, target_qty, memo?}]` 리스트를 담고, `status` 는 `pending`/`collecting`/`done`/`error` 중 하나이며 기본값은 `pending` 이다. `tenant_id` 는 조회 성능을 위한 비정규화 컬럼이며 shop_id 의 tenant_id 와 일치해야 한다.

#### Scenario: 발주 주문 생성
- **WHEN** 인증된 사용자가 `POST /api/v1/procurement/orders` 로 `{shop_id: 42, items: [{sku: "coke-500ml-30", keyword: "코카콜라 500ml 30개", target_qty: 1}, ...]}` 를 요청한다
- **THEN** 시스템은 `shop_id=42` 가 요청자의 `tenant_id` 소속인지 검증한 후, `status='pending'` 으로 주문을 생성하고 HTTP 201 + `{id, shop_id, tenant_id, items, status, created_at}` 을 반환한다

#### Scenario: 다른 테넌트의 shop_id 로 생성 시도
- **WHEN** 테넌트 A 의 사용자가 테넌트 B 소속 `shop_id` 로 주문을 생성하려 한다
- **THEN** 시스템은 HTTP 404 `{detail: "shop_not_found", code: "NOT_FOUND"}` 를 반환한다

#### Scenario: 빈 items 배열
- **WHEN** `items: []` 또는 `items` 필드가 누락된 요청이 온다
- **THEN** 시스템은 HTTP 422 `{detail: <pydantic 에러>, code: "INVALID_REQUEST"}` 를 반환한다

### Requirement: 발주 주문 목록 조회

시스템은 `GET /api/v1/procurement/orders?shop_id=<id>&status=<s>&limit=<n>&offset=<m>` 엔드포인트를 제공해야 한다(MUST). 응답은 현재 테넌트 소속 주문만 포함하며 `created_at DESC` 로 정렬된다. `limit` 기본 50, 최대 200.

#### Scenario: 정상 목록 조회
- **WHEN** 인증된 사용자가 `GET /api/v1/procurement/orders?limit=10` 를 호출한다
- **THEN** 시스템은 HTTP 200 + `{items: [...최신 10건], total: <count>, limit: 10, offset: 0}` 을 반환하며, 쿼리는 `WHERE tenant_id = :current_tenant_id` 필터를 포함한다

#### Scenario: shop_id 필터
- **WHEN** `?shop_id=42` 파라미터를 지정한다
- **THEN** 시스템은 해당 shop 에 속한 주문만 반환하며, 해당 shop 이 다른 테넌트 소속이면 404 를 반환한다

#### Scenario: status 필터
- **WHEN** `?status=done` 파라미터를 지정한다
- **THEN** 시스템은 `status='done'` 인 주문만 반환한다

### Requirement: 발주 주문 단건 조회

시스템은 `GET /api/v1/procurement/orders/{id}` 엔드포인트를 제공해야 한다(MUST).

#### Scenario: 정상 조회
- **WHEN** 인증된 사용자가 자신의 테넌트 소속 `order_id` 로 조회한다
- **THEN** 시스템은 HTTP 200 + 주문 상세(`items` 전체 포함)를 반환한다

#### Scenario: 존재하지 않거나 타 테넌트 소속
- **WHEN** 존재하지 않는 `order_id` 또는 타 테넌트 소속 `order_id` 로 조회한다
- **THEN** 시스템은 HTTP 404 `{detail: "order_not_found", code: "NOT_FOUND"}` 를 반환한다 (소속 테넌트를 노출하지 않음)

### Requirement: 발주 주문 상태 갱신

시스템은 `PATCH /api/v1/procurement/orders/{id}` 를 통해 `status` 를 갱신할 수 있어야 한다(SHALL). 상태 전이는 `pending → collecting → done` 또는 임의 상태 → `error` 만 허용한다.

#### Scenario: 정상 상태 전이
- **WHEN** 사용자가 `pending` 주문을 `PATCH {status: "collecting"}` 로 갱신한다
- **THEN** 시스템은 `status = 'collecting'`, `updated_at = NOW()` 로 갱신하고 HTTP 200 을 반환한다

#### Scenario: 불허 상태 전이
- **WHEN** `done` 주문을 `{status: "pending"}` 으로 되돌리려 한다
- **THEN** 시스템은 HTTP 400 `{detail: "invalid_status_transition", code: "INVALID_STATE"}` 를 반환한다

### Requirement: 테넌트 월간 쿼터 소비

시스템은 주문 생성 시 테넌트 월간 API 쿼터 카운터를 소비해야 한다(SHALL). 쿼터 초과 시 HTTP 429 를 반환하고 주문을 생성하지 않는다.

#### Scenario: 쿼터 여유 있음
- **WHEN** 테넌트의 이번달 API 호출 합계가 `api_quota_monthly - 1` 이하이며 사용자가 주문을 생성한다
- **THEN** 시스템은 카운터를 +1 증가시키고 주문을 정상 생성한다

#### Scenario: 쿼터 초과
- **WHEN** 테넌트의 이번달 API 호출 합계가 `api_quota_monthly` 에 도달한 상태에서 사용자가 주문을 생성한다
- **THEN** 시스템은 HTTP 429 `{detail: "tenant_quota_exceeded", code: "QUOTA_EXCEEDED"}` 를 반환하고 주문을 생성하지 않는다

### Requirement: 주문 삭제

시스템은 `DELETE /api/v1/procurement/orders/{id}` 를 제공해야 한다(SHALL). 삭제는 `CASCADE` 로 연결된 `procurement_results` 도 함께 제거한다.

#### Scenario: 정상 삭제
- **WHEN** 인증된 사용자가 자신의 테넌트 소속 주문을 삭제한다
- **THEN** 시스템은 `procurement_orders` 와 연관된 `procurement_results` 를 전부 삭제하고 HTTP 204 를 반환한다

#### Scenario: 타 테넌트 주문 삭제 시도
- **WHEN** 테넌트 A 의 사용자가 테넌트 B 소속 주문을 `DELETE` 호출한다
- **THEN** 시스템은 HTTP 404 를 반환하고 데이터에 변경을 가하지 않는다
