## ADDED Requirements

### Requirement: 플랜 선택과 구독 생성

시스템은 사장(tenant)이 선택한 플랜 코드(`starter`/`business`/`multi_shop`)와 토스 빌링키를 기반으로 구독을 생성해야 한다(MUST). 구독 생성 시 첫 결제를 즉시 수행하며 성공 시에만 `subscriptions.status = 'active'`로 기록한다. `franchise` 플랜은 `enabled=False`로 가입을 차단해야 한다(MUST).

#### Scenario: 유효한 플랜으로 신규 구독을 생성한다
- **WHEN** 사장이 `plan=starter`와 유효한 `billing_key`로 `POST /api/v1/billing/subscribe`를 호출한다
- **THEN** 시스템은 토스 API로 즉시 첫 결제(₩19,900)를 수행하고 `subscriptions` 레코드를 `status='active'`, `next_billing_at = 오늘 + 1 month`로 생성해 반환한다

#### Scenario: 첫 결제가 실패한다
- **WHEN** 플랜 선택 후 첫 결제가 카드 한도 초과로 실패한다
- **THEN** 시스템은 `subscriptions` 레코드를 생성하지 않고 HTTP 402 + `{detail: "first_charge_failed", code: "PAYMENT_DECLINED"}`을 반환한다

#### Scenario: Franchise 플랜 가입 시도
- **WHEN** 사장이 `plan=franchise`로 구독 생성을 시도한다
- **THEN** 시스템은 HTTP 403 + `{detail: "plan_not_available", code: "PLAN_DISABLED"}`를 반환한다

#### Scenario: 동일 테넌트의 중복 활성 구독 방지
- **WHEN** 이미 `active` 또는 `past_due` 상태의 구독을 가진 테넌트가 신규 구독을 시도한다
- **THEN** 시스템은 HTTP 409 + `{detail: "active_subscription_exists", code: "DUPLICATE_SUBSCRIPTION"}`을 반환한다

### Requirement: 구독 상태 전이

시스템은 구독 상태를 `active → past_due → suspended → cancelled` 순으로만 전이시켜야 한다(MUST). 결제 성공 시 `past_due → active` 복귀는 허용된다. 이미 `cancelled`된 구독은 상태 변경 없이 신규 레코드로만 재가입 가능하다.

#### Scenario: 첫 결제 실패로 past_due 전이
- **WHEN** 정기결제(자동)가 1회 실패한다
- **THEN** 시스템은 구독을 `past_due`로 전이하고 `billing_retries` 레코드를 INSERT한다

#### Scenario: 재시도 성공으로 active 복귀
- **WHEN** `past_due` 구독의 `billing_retries` 건이 성공한다
- **THEN** 시스템은 구독을 `active`로 복귀시키고 `next_billing_at`을 재계산한다

#### Scenario: 3회 재시도 실패로 suspended 전이
- **WHEN** 동일 구독의 `billing_retries.attempt_count > BILLING_MAX_RETRIES`(기본 3)에 도달한다
- **THEN** 시스템은 구독을 `suspended`로 전이하고 해당 테넌트의 앱 접근을 차단한다

#### Scenario: 잘못된 전이 시도 차단
- **WHEN** 코드가 `cancelled` 구독을 `active`로 되돌리려 시도한다
- **THEN** 시스템은 `InvalidStateTransitionError`를 발생시키고 DB 변경을 롤백한다

### Requirement: 구독 해지와 cycle 종료

시스템은 사장의 해지 요청을 즉시 반영하지 않고 현재 billing cycle 종료 시점까지 `active` 상태를 유지해야 한다(MUST). 해지 요청 시각은 `subscriptions.cancelled_at`에 기록한다. cycle 종료 시 상태를 `cancelled`로 최종 전이한다.

#### Scenario: 해지 요청 후 cycle 종료까지 사용 가능
- **WHEN** 사장이 `POST /api/v1/billing/cancel`을 호출한다 (next_billing_at = 2026-05-15)
- **THEN** 시스템은 `cancelled_at = NOW()`를 기록하고 2026-05-15 전까지 구독을 `active`로 유지, 2026-05-15에 `cancelled`로 전이한다

#### Scenario: 해지된 구독의 자동결제 차단
- **WHEN** 정기결제 스케줄러가 `cancelled_at IS NOT NULL` 구독을 발견한다
- **THEN** 시스템은 해당 구독에 자동결제를 시도하지 않고 `next_billing_at` 시점에 `cancelled` 상태로 전이만 수행한다

### Requirement: 구독 상태 조회

시스템은 `GET /api/v1/billing/status`를 통해 현재 구독의 플랜·상태·다음 결제일·결제 금액을 반환해야 한다(MUST). 활성 구독이 없는 테넌트는 `{subscription: null}`을 반환한다.

#### Scenario: 활성 구독이 있다
- **WHEN** `status='active'`인 구독이 있는 테넌트가 상태를 조회한다
- **THEN** 응답은 `{subscription: {plan, status, amount_krw, next_billing_at, cancelled_at}}`을 포함한다

#### Scenario: 구독이 없다
- **WHEN** 구독 이력이 없는 테넌트가 상태를 조회한다
- **THEN** 응답은 `{subscription: null}`을 반환한다

### Requirement: 결제 내역 조회

시스템은 `GET /api/v1/billing/invoices?limit=&offset=`를 통해 해당 테넌트의 `payment_events` 중 `event_type IN ('charge_success', 'charge_failed')` 레코드를 최신순으로 반환해야 한다(MUST).

#### Scenario: 정상 페이지네이션
- **WHEN** 사장이 `limit=10&offset=0`으로 조회한다
- **THEN** 응답은 최신 10건의 결제 내역(`amount_krw`, `processed_at`, `status`)과 총 건수(`total`)를 반환한다

#### Scenario: 다른 테넌트의 내역 접근 차단
- **WHEN** 테넌트 A가 테넌트 B의 결제 내역을 조회하려 시도한다
- **THEN** 시스템은 tenant 격리 로직에 따라 테넌트 A의 내역만 반환한다(B의 건은 노출되지 않는다)

### Requirement: 플랜 한도 강제

시스템은 플랜별 한도(`orders_per_month`, `max_shops`)를 비즈니스 로직에서 강제해야 한다(MUST). Starter 플랜 사용자가 월 50건 발주에 도달하면 신규 발주 생성을 차단하고, 업그레이드 CTA를 응답에 포함한다.

#### Scenario: Starter 한도 초과 발주
- **WHEN** Starter 구독 테넌트가 당월 50건째 발주 후 51번째 발주를 시도한다
- **THEN** 시스템은 HTTP 403 + `{detail: "plan_limit_exceeded", code: "ORDERS_QUOTA_EXCEEDED", upgrade_to: "business"}`를 반환한다

#### Scenario: Multi-Shop 가게 수 한도
- **WHEN** Multi-Shop 구독 테넌트가 4번째 가게를 등록하려 시도한다
- **THEN** 시스템은 HTTP 403 + `{detail: "plan_limit_exceeded", code: "SHOPS_QUOTA_EXCEEDED", upgrade_to: "franchise"}`를 반환한다

#### Scenario: Business 플랜은 발주 무제한
- **WHEN** Business 구독 테넌트가 월 1000건 발주를 시도한다
- **THEN** 시스템은 제한 없이 허용한다(`orders_per_month = None`)
