## ADDED Requirements

### Requirement: 매일 정기결제 배치

시스템은 Arq 크론 태스크 `charge_due_subscriptions`를 매일 새벽 2시(KST, `0 2 * * *`)에 실행해 `subscriptions WHERE status = 'active' AND next_billing_at <= NOW() AND cancelled_at IS NULL` 대상에게 자동 결제를 수행해야 한다(MUST). 다중 워커 환경에서는 `SELECT ... FOR UPDATE SKIP LOCKED`로 경합을 방지한다.

#### Scenario: 예정일 도래한 구독 결제
- **WHEN** `next_billing_at = 2026-05-01 09:00`인 활성 구독이 있고 2026-05-02 02:00 크론이 실행된다
- **THEN** 시스템은 해당 구독에 토스 빌링 API를 호출하고 성공 시 `next_billing_at = 2026-06-01`, `payment_events.charge_success` INSERT를 수행한다

#### Scenario: 해지 요청된 구독은 결제 스킵
- **WHEN** `cancelled_at IS NOT NULL`이고 `next_billing_at`이 도래한 구독을 크론이 발견한다
- **THEN** 시스템은 결제를 시도하지 않고 구독 상태를 `cancelled`로 최종 전이한다

#### Scenario: 결제 실패 시 재시도 큐잉
- **WHEN** 정기결제 대상 구독의 결제가 실패한다
- **THEN** 시스템은 구독을 `past_due`로 전이하고 `billing_retries` INSERT(`next_retry_at = NOW() + BILLING_RETRY_INTERVAL_DAYS`)를 수행한다

#### Scenario: 다중 워커 경합 방지
- **WHEN** 동일 크론이 2개 워커에서 동시 실행된다
- **THEN** 각 워커는 `FOR UPDATE SKIP LOCKED`로 잠긴 행을 건너뛰고 중복 결제가 발생하지 않는다

### Requirement: 결제 실패 재시도 배치

시스템은 Arq 크론 태스크 `retry_failed_billings`를 매일 새벽 2시 30분(KST, `30 2 * * *`)에 실행해 `billing_retries WHERE resolved_at IS NULL AND next_retry_at <= NOW()` 대상에게 재결제를 시도해야 한다(MUST).

#### Scenario: 재시도 성공
- **WHEN** `attempt_count = 1`인 `billing_retries` 건의 재결제가 성공한다
- **THEN** 시스템은 `resolved_at = NOW()` 기록, 구독 `active` 복귀, `next_billing_at += 1 month`로 갱신한다

#### Scenario: 재시도 실패 → 다음 시도 예약
- **WHEN** `attempt_count = 1` 건의 재결제가 실패하고 `attempt_count + 1 <= BILLING_MAX_RETRIES`(기본 3)이다
- **THEN** 시스템은 `attempt_count = 2`, `next_retry_at = NOW() + 3 days`, `last_error` 갱신한다

#### Scenario: 최대 재시도 횟수 초과 → suspended
- **WHEN** `attempt_count = 3` 건의 재결제가 실패해 `attempt_count + 1 > BILLING_MAX_RETRIES`에 도달한다
- **THEN** 시스템은 `resolved_at = NOW()` 기록, 구독 `suspended` 전이, 사장에게 결제 정보 재등록 알림을 전송한다

#### Scenario: 해지된 구독의 미해결 재시도는 종료
- **WHEN** `billing_retries.resolved_at IS NULL` 상태에서 해당 구독이 `cancelled`로 전이된다
- **THEN** 재시도 크론은 해당 건을 `resolved_at = NOW()`, `last_error = 'subscription_cancelled'`로 종결하고 결제를 시도하지 않는다

### Requirement: 배치 실행 로깅과 메트릭

시스템은 각 크론 실행 시 처리 대상 건수·성공 건수·실패 건수·총 소요 시간을 structlog로 기록하고 Prometheus 커스텀 메트릭으로 노출해야 한다(MUST). 관측 지표: `billing_charge_total{status=success|failed}`, `billing_retry_count{result=success|failed|exhausted}`, `scheduled_billing_duration_seconds`.

#### Scenario: 정상 실행 로그
- **WHEN** `charge_due_subscriptions` 크론이 10건을 처리한다 (성공 8건, 실패 2건)
- **THEN** 시스템은 `{"cron": "charge_due_subscriptions", "processed": 10, "success": 8, "failed": 2, "duration_sec": 12.3}` 형태의 structlog INFO 레코드를 남긴다

#### Scenario: 대량 실패 시 알림
- **WHEN** 한 번의 크론 실행에서 실패율이 50%를 초과한다
- **THEN** 시스템은 Sentry에 `bulk_billing_failure` 경고 이벤트를 전송하고 운영자에게 알림한다 `[교차검증 필요]` 알림 임계치(50%)는 pilot 데이터 기반 재조정

### Requirement: 배치 중복 실행 방지

시스템은 동일 날짜(KST 기준)에 같은 크론이 중복 실행되지 않도록 Redis 키(`cron:lock:charge_due:{YYYYMMDD}`, TTL 23시간)로 분산 락을 획득해야 한다(MUST). 락 획득 실패 시 조용히 종료한다.

#### Scenario: 크론 중복 트리거 방지
- **WHEN** 스케줄러 설정 오류로 `charge_due_subscriptions`가 같은 날 2회 트리거된다
- **THEN** 두 번째 실행은 Redis 락 획득 실패로 즉시 종료되고 결제 처리를 시도하지 않는다

### Requirement: 수동 트리거 CLI

시스템은 관리자가 크론 실행을 수동으로 트리거할 수 있는 CLI 명령(`python -m backend.app.billing.scheduler charge-due` 및 `retry-failed`)을 제공해야 한다(MUST). 긴급 복구·테스트·운영 대응 시 사용한다.

#### Scenario: 관리자가 수동으로 미처리 건 재시도
- **WHEN** 운영자가 장애 복구 후 `python -m backend.app.billing.scheduler retry-failed`를 실행한다
- **THEN** 시스템은 `retry_failed_billings` 로직을 즉시 실행하고 처리 결과를 콘솔에 출력한다

#### Scenario: 수동 트리거도 중복 방지 락 준수
- **WHEN** 크론이 실행 중인 동안 관리자가 수동 트리거를 시도한다
- **THEN** Redis 분산 락 충돌로 즉시 종료되고 "already running" 메시지를 출력한다
