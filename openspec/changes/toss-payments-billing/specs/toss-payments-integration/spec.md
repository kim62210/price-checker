## ADDED Requirements

### Requirement: 빌링키 발급

시스템은 프론트(카드등록 위젯)에서 받은 `authKey`와 `customerKey`를 토스 API(`POST /v1/billing/authorizations/issue`)에 전달하고 빌링키를 발급받아야 한다(MUST). 빌링키는 `subscriptions.billing_key` 컬럼에 저장하며 카드번호는 절대 저장하지 않는다. 인증은 HTTP Basic Auth(`secret_key:`)로 수행한다.

#### Scenario: 정상 authKey로 빌링키를 발급한다
- **WHEN** 프론트가 `authKey`, `customerKey`를 백엔드에 전달하고 빌링키 발급을 요청한다
- **THEN** 시스템은 토스 API로 교환 요청을 보내 `billingKey`를 획득한 뒤 `subscriptions.billing_key`에 저장하고 200 OK를 반환한다

#### Scenario: 만료된 authKey
- **WHEN** 재사용 또는 만료된 `authKey`로 교환 요청을 한다
- **THEN** 토스가 4xx를 반환하고 시스템은 HTTP 400 + `{detail: "auth_key_invalid", code: "INVALID_AUTH_KEY"}`를 반환한다

#### Scenario: 카드번호는 서버에 절대 도달하지 않는다
- **WHEN** 빌링키 발급 전 구간의 네트워크 로그를 감사한다
- **THEN** 요청 body·헤더·DB 어느 곳에도 카드번호(PAN)·CVV·유효기간 필드가 존재하지 않는다(`authKey`와 `customerKey`만 존재한다)

### Requirement: 빌링키 결제 요청

시스템은 저장된 빌링키로 `POST /v1/billing/{billingKey}`를 호출해 결제를 수행해야 한다(MUST). 요청 본문에는 `amount`, `orderId`, `orderName`, `customerKey`를 포함한다. `orderId`는 멱등성 보장을 위해 구독 ID와 결제 주기를 조합한 결정론적 값이어야 한다(예: `sub_{subscription_id}_{YYYYMMDD}`).

#### Scenario: 정기결제 성공
- **WHEN** 활성 구독의 `next_billing_at`이 도래해 자동결제를 수행한다
- **THEN** 시스템은 토스 API 동기 응답에서 `status = DONE`을 확인하고 `payment_events`에 `charge_success` 레코드를 INSERT한다

#### Scenario: 카드 한도 초과로 결제 실패
- **WHEN** 토스 API가 `code = "EXCEED_MAX_AMOUNT"` 등 실패 응답을 반환한다
- **THEN** 시스템은 `payment_events`에 `charge_failed` 레코드와 raw_payload를 INSERT하고 `billing_retries`에 재시도 큐잉한다

#### Scenario: 토스 API 일시 장애
- **WHEN** 토스 API가 HTTP 5xx를 반환한다
- **THEN** 시스템은 지수 백오프 + jitter로 최대 3회 재시도하고, 그래도 실패하면 `billing_retries` INSERT로 폴백한다

#### Scenario: 동일 orderId 중복 호출
- **WHEN** 이미 성공한 `orderId`로 다시 결제를 시도한다
- **THEN** 토스가 중복을 감지해 4xx 반환, 시스템은 중복 결제로 간주하고 기존 `payment_events` 레코드를 재활용한다 `[교차검증 필요]` 토스 빌링 API 중복 orderId 동작 공식 확인

### Requirement: 빌링키 해지

시스템은 구독이 `cancelled`로 최종 전이되는 시점에 토스 빌링키 해지 API를 호출해 빌링키를 무효화해야 한다(MUST). 해지 호출 실패는 로그로만 기록하고 구독 상태 전이는 차단하지 않는다.

#### Scenario: 구독 cancelled 시 빌링키 해지 시도
- **WHEN** 해지 요청된 구독이 cycle 종료 시 `cancelled`로 전이된다
- **THEN** 시스템은 토스 빌링키 해지 API를 호출하고 성공 시 `subscriptions.billing_key = NULL`로 갱신한다

#### Scenario: 빌링키 해지 API 실패
- **WHEN** 토스 빌링키 해지 API가 실패한다
- **THEN** 시스템은 에러 로깅 + Sentry 알림만 수행하고 구독 `cancelled` 상태는 그대로 유지한다

### Requirement: 테스트/운영 키 혼용 방지

시스템은 `ENV=production`이 아닌 환경에서 운영 키(`live_sk_*`, `live_ck_*`)가 주입되면 애플리케이션 시작 시 즉시 예외를 발생시키고 기동을 중단해야 한다(MUST). 운영 환경에서 테스트 키 주입도 동일하게 차단한다.

#### Scenario: 스테이징에서 운영 키 주입
- **WHEN** `ENV=staging`이고 `TOSS_SECRET_KEY=live_sk_xxx`가 설정된다
- **THEN** 시스템은 시작 시 `ConfigurationError("production key injected in non-production environment")`를 발생시키고 즉시 종료한다

#### Scenario: 프로덕션에서 테스트 키 주입
- **WHEN** `ENV=production`이고 `TOSS_SECRET_KEY=test_sk_xxx`가 설정된다
- **THEN** 시스템은 시작 시 `ConfigurationError("test key in production environment")`를 발생시키고 즉시 종료한다

### Requirement: 토스 API 호출 탄력성

시스템은 토스 API 호출에 httpx 타임아웃(`connect=3, read=10, write=3, pool=5`)과 tenacity 재시도(지수 백오프, 최대 3회, 429/5xx 한정)를 적용해야 한다(MUST).

#### Scenario: HTTP 429 수신 시 재시도
- **WHEN** 토스 API가 HTTP 429를 반환한다
- **THEN** 시스템은 지수 백오프로 최대 3회 재시도하고 성공 시 결과를 반환한다

#### Scenario: 재시도 모두 실패
- **WHEN** 3회 재시도 모두 실패한다
- **THEN** 시스템은 `TossApiError` 예외를 발생시키고 호출자에게 전파한다(정기결제 태스크는 이를 받아 `billing_retries` 큐잉 처리)
