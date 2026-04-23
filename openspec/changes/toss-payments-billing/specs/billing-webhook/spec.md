## ADDED Requirements

### Requirement: Webhook 서명 검증

시스템은 `POST /api/v1/billing/webhook`으로 수신한 요청의 HMAC 서명을 `TOSS_WEBHOOK_SECRET`으로 검증해야 한다(MUST). 서명이 일치하지 않으면 HTTP 401을 반환하고 본문 처리를 차단한다. 서명 검증은 raw body 기준으로 수행하며 JSON 역직렬화 전에 수행한다.

#### Scenario: 유효한 서명으로 Webhook 수신
- **WHEN** 토스가 유효한 `toss-signature` 헤더와 함께 Webhook을 POST한다
- **THEN** 시스템은 서명을 검증하고 200 OK 반환과 함께 이벤트를 처리한다

#### Scenario: 잘못된 서명
- **WHEN** 공격자가 위조된 서명으로 Webhook 엔드포인트를 호출한다
- **THEN** 시스템은 HTTP 401 + `{detail: "signature_invalid"}`를 반환하고 Sentry에 경고 이벤트를 전송한다

#### Scenario: 서명 헤더 누락
- **WHEN** 서명 헤더가 없는 요청이 들어온다
- **THEN** 시스템은 HTTP 401 + `{detail: "signature_missing"}`을 반환한다

### Requirement: Webhook 멱등 처리

시스템은 동일한 `event_id` 또는 `toss_order_id`로 중복 수신되는 Webhook을 중복 처리 없이 1회만 반영해야 한다(MUST). 중복 감지는 2단계로 수행한다: (1) Redis SETNX(`webhook:processed:{event_id}`, TTL 24h)로 즉시 차단, (2) `payment_events.toss_order_id` UNIQUE 제약으로 DB 레벨 방어.

#### Scenario: 동일 event_id 중복 수신
- **WHEN** 토스가 같은 `event_id`의 Webhook을 5초 간격으로 2회 전송한다
- **THEN** 첫 번째는 정상 처리되고(200 OK), 두 번째는 Redis SETNX 실패로 즉시 200 OK만 반환되며 DB 변경은 발생하지 않는다

#### Scenario: Redis 장애로 SETNX 누락 시 DB 중복 INSERT 시도
- **WHEN** Redis 장애 상황에서 중복 Webhook이 수신되어 DB INSERT까지 진행된다
- **THEN** `payment_events.toss_order_id` UNIQUE 제약으로 `ON CONFLICT DO NOTHING`이 발동해 중복 레코드가 생성되지 않는다

#### Scenario: 처리 실패 시 2xx 외 반환으로 토스 재시도 유도
- **WHEN** Webhook 처리 중 애플리케이션 예외가 발생한다
- **THEN** 시스템은 HTTP 500을 반환하여 토스의 자동 재시도를 유도한다(후속 멱등 로직이 중복을 방어)

### Requirement: PAYMENT.DONE 이벤트 처리

시스템은 `PAYMENT.DONE` 이벤트 수신 시 해당 `orderId`와 매핑되는 구독을 찾아 `payment_events`에 `charge_success` 레코드를 INSERT하고, 구독이 `past_due`였다면 `active`로 복귀시키며 `next_billing_at`을 1개월 뒤로 갱신해야 한다(MUST).

#### Scenario: 정기결제 성공 Webhook
- **WHEN** 정기결제 성공 후 토스가 `PAYMENT.DONE` Webhook을 전송한다
- **THEN** 시스템은 `payment_events.charge_success` INSERT, `subscriptions.status = 'active'`, `next_billing_at += 1 month`로 갱신한다

#### Scenario: 매칭되는 구독이 없는 Webhook
- **WHEN** 알 수 없는 `orderId`의 `PAYMENT.DONE` Webhook을 수신한다
- **THEN** 시스템은 로그로만 기록하고 200 OK 반환(DB 변경 없음)

### Requirement: PAYMENT.FAILED 이벤트 처리

시스템은 `PAYMENT.FAILED` 이벤트 수신 시 `payment_events.charge_failed` INSERT하고, 구독 상태를 `past_due`로 전이하며 `billing_retries` 큐에 재시도를 예약해야 한다(MUST). 이미 동일 구독에 미해결 `billing_retries`가 있으면 중복 큐잉하지 않는다.

#### Scenario: 정기결제 실패 Webhook
- **WHEN** 카드 한도 초과로 `PAYMENT.FAILED` Webhook이 수신된다
- **THEN** 시스템은 `payment_events.charge_failed` INSERT, `subscriptions.status = 'past_due'`, `billing_retries` INSERT(`next_retry_at = NOW() + 3 days`)를 수행한다

#### Scenario: 이미 재시도 큐잉된 구독에 재실패 이벤트
- **WHEN** `billing_retries.resolved_at IS NULL` 상태에서 추가 `PAYMENT.FAILED` Webhook이 도착한다
- **THEN** 시스템은 중복 큐잉 없이 기존 `billing_retries.attempt_count`를 유지하고 `last_error`만 갱신한다

### Requirement: BILLING.CANCELED 이벤트 처리

시스템은 `BILLING.CANCELED` 이벤트 수신 시(토스 측에서 빌링키가 해지된 경우) 해당 `subscriptions.billing_key`를 NULL로 설정하고, 활성 상태라면 즉시 `suspended`로 전이해야 한다(MUST).

#### Scenario: 사용자가 토스 고객센터로 직접 빌링키 해지
- **WHEN** 우리 시스템을 거치지 않고 사용자가 토스에서 직접 빌링키를 해지해 `BILLING.CANCELED` Webhook이 수신된다
- **THEN** 시스템은 `subscriptions.billing_key = NULL`, `status = 'suspended'`로 갱신하고 사장에게 결제 정보 재등록을 안내하는 알림을 전송한다

#### Scenario: 이미 우리 측에서 해지된 빌링키
- **WHEN** 우리 시스템이 선제적으로 해지한 빌링키에 대해 `BILLING.CANCELED` Webhook이 뒤늦게 도착한다
- **THEN** 시스템은 중복 전이 없이 200 OK만 반환한다

### Requirement: Webhook 원본 로깅

시스템은 모든 Webhook 요청의 raw body와 서명 헤더를 `payment_events.raw_payload`(JSONB)에 저장해야 한다(MUST). 이는 사후 감사·분쟁 대응·토스 측 재처리 요청 시 필요하다.

#### Scenario: 결제 분쟁 발생 시 원본 조회
- **WHEN** 고객이 결제 분쟁을 제기해 해당 거래의 원본 Webhook 본문이 필요하다
- **THEN** 관리자는 `payment_events.raw_payload`에서 토스가 보낸 원본 JSON을 그대로 조회할 수 있다
