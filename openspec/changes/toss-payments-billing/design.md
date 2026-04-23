## Context

- 사용자(소매점 사장)는 월 단위 구독으로 서비스를 이용한다. PG 결제 실패로 인한 이탈을 최소화하면서, 카드 정보를 서버에 저장하지 않는 안전한 과금 인프라가 필요하다.
- 한국 시장 PG 후보 비교:
  - **토스페이먼츠 빌링 v2**(채택): 카드 3.4%+VAT / 계좌이체 2.0%(최소 ₩200), 가입비 ₩22만 + 연 ₩11만. Webhook 멱등키 공식 지원. 문서 품질 업계 1위. 개인사업자 신규 등록 원스톱. 채널톡·Flex·당근 등 B2B SaaS 레퍼런스 풍부.
  - **포트원(구 아임포트)**: PG 통합 허브(여러 PG 단일 API). 수수료 +0.5% 정도. B2B 월 구독에는 오버엔지니어링.
  - **KCP 빌링**: 수수료 경쟁력 있으나 문서·개발자 경험이 토스 대비 열위.
  - **나이스페이먼츠·KG이니시스**: 전통 PG. SaaS 친화적 빌링 API 경험 부족.
- 법적/컴플라이언스 맥락:
  - PCI DSS SAQ-A: 카드번호가 우리 서버를 통과하지 않으면(위젯이 토스 도메인으로 직접 전송) 가장 낮은 수준의 자가평가만 필요.
  - 개인정보보호법: 이메일·사업자번호 등은 `pivot-backend-multi-tenant`의 암호화 정책에 위임.
  - 전자상거래법: 정기결제 해지 창구 명시 필요 → `POST /api/v1/billing/cancel` + UI "구독 해지" 버튼.
- 운영 환경: FastAPI + Postgres 16 + Redis 7 + Arq 워커. 기존 `pivot-backend-multi-tenant`에서 구축된 멀티테넌트 스키마(`tenants`) 위에 구축.

## Goals / Non-Goals

**Goals:**
- 토스페이먼츠 빌링 v2로 월 구독 과금을 자동화한다.
- 카드번호를 절대 서버에 저장하지 않는다(빌링키만 보관).
- Webhook 수신·멱등 처리·서명 검증으로 결제 상태 불일치를 제거한다.
- 결제 실패 시 3일 간격 3회 자동 재시도로 일시적 네트워크/한도 이슈를 자연 복구한다.
- 구독 상태(`active`/`past_due`/`suspended`/`cancelled`)를 미들웨어에서 조회해 접근 제어한다.
- Arq 크론으로 매일 정기결제 배치를 무인 실행한다.
- 플랜별 한도(발주 건수·가게 수)는 DB + 미들웨어로 강제한다.

**Non-Goals:**
- 다중 PG 동시 지원(포트원 같은 추상화 계층 없음 — 토스 단일 PG 고정).
- 환불(pro-rated 포함), 일할 계산, 플랜 다운그레이드 즉시 반영 — v1은 **cycle 종료까지 유지 후 다음 주기부터 반영**.
- 세금계산서 자동 발행 — v1에서는 관리자 수동 처리(Hometax 등).
- 쿠폰/프로모션 코드 시스템 — Starter 할인가는 `plans.py` 상수로만 관리, 코드 입력 UI 없음.
- 계좌이체(2.0%) 지원 — v1은 카드 한정(자동 정기결제 요구).
- Franchise 플랜 실제 구현 — Post-MVP(현재는 `plans.py`에 상수로만 선언).
- 카드사 직접 연동, 해외 결제, 다중 통화.

## Decisions

### 1. PG: 토스페이먼츠 빌링 v2 단독 채택
- `httpx.AsyncClient` + HTTP Basic Auth(secret_key + `:`) + Webhook HMAC 검증의 단순한 통합 패턴.
- 카드등록은 토스 JS 위젯(프론트)에서 수행 → 백엔드는 `authKey`만 받아 `POST /v1/billing/authorizations/issue`로 빌링키 교환.
- 이후 모든 결제는 `POST /v1/billing/{billingKey}` (서버 → 토스) 호출로 진행. 카드 정보는 우리 서버에 절대 흘러들지 않는다.

### 2. DB 스키마
`backend/app/billing/models.py`에 3개 테이블을 정의한다. 모든 FK는 `tenants.id` 기준.

```sql
CREATE TABLE subscriptions (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    plan VARCHAR(32) NOT NULL,                      -- 'starter' / 'business' / 'multi_shop' / 'franchise'
    billing_key VARCHAR(255) UNIQUE,                -- 토스가 발급, 카드 정보는 토스에 저장
    status VARCHAR(32) NOT NULL DEFAULT 'active',   -- active / past_due / suspended / cancelled
    amount_krw INT NOT NULL,                        -- 월 결제 금액 (할인 반영 후)
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    next_billing_at TIMESTAMP NOT NULL,             -- 다음 자동결제 일시 (KST)
    cancelled_at TIMESTAMP,                         -- 해지 요청 시각 (cycle 종료까지는 active)
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_subscriptions_active_tenant
    ON subscriptions(tenant_id) WHERE status IN ('active', 'past_due');

CREATE TABLE payment_events (
    id BIGSERIAL PRIMARY KEY,
    subscription_id BIGINT NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    event_type VARCHAR(32) NOT NULL,                -- charge_success / charge_failed / subscribe / cancel / webhook_received
    amount_krw INT,
    toss_payment_key VARCHAR(255),
    toss_order_id VARCHAR(255) UNIQUE,              -- 멱등 보장용
    raw_payload JSONB NOT NULL,                     -- 토스 응답 원본 저장
    processed_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_payment_events_subscription ON payment_events(subscription_id, processed_at DESC);

CREATE TABLE billing_retries (
    id BIGSERIAL PRIMARY KEY,
    subscription_id BIGINT NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    attempt_count INT NOT NULL DEFAULT 1,
    next_retry_at TIMESTAMP NOT NULL,
    last_error TEXT,
    resolved_at TIMESTAMP,                          -- 성공 또는 최종 실패로 종료된 시각
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_billing_retries_pending
    ON billing_retries(next_retry_at) WHERE resolved_at IS NULL;
```

- `subscriptions.billing_key`는 토스가 발급하는 문자열. 분실 시 재발급 불가 → 위험 노출면 최소화를 위해 DB 컬럼 수준 암호화는 선택(환경변수 `BILLING_KEY_ENCRYPTION` on 시 적용) `[교차검증 필요]` 토스 빌링키 재발급 정책 공식 문서 확인.
- `payment_events.toss_order_id`에 UNIQUE 제약 → Webhook 중복 수신 시 INSERT 충돌로 자연 멱등.

### 3. 플랜 정의 (`plans.py`)
```python
PLANS = {
    "starter":    Plan(code="starter", price_krw=19_900,  pilot_price_krw=19_900,  orders_per_month=50,  max_shops=1),
    "business":   Plan(code="business", price_krw=49_900,  pilot_price_krw=19_900,  orders_per_month=None, max_shops=1),
    "multi_shop": Plan(code="multi_shop", price_krw=99_900, pilot_price_krw=99_900, orders_per_month=None, max_shops=3),
    "franchise":  Plan(code="franchise", price_krw=300_000, pilot_price_krw=300_000, orders_per_month=None, max_shops=None),  # Post-MVP
}
```
- `pilot_price_krw`는 pilot 기간 한정 가격. `settings.PILOT_MODE` on 시 적용.
- Franchise는 `enabled=False` 플래그로 가입 차단(Post-MVP).

### 4. 결제 플로우 (시퀀스 다이어그램)
```
사장(Tauri/Web)             백엔드                     토스페이먼츠
  │                          │                            │
  │ 1. 플랜 선택              │                            │
  ├─────────────────────────▶│                            │
  │                          │ 2. CLIENT_KEY 전달          │
  │◀─────────────────────────┤                            │
  │ 3. 토스 카드등록 위젯 호출 (JS SDK)                     │
  ├──────────────────────────────────────────────────────▶│
  │                          │   4. 카드번호 (우리 서버 미경유)
  │                          │                            │
  │◀──────────────────────────────────────────────────────┤
  │ 5. authKey, customerKey                                │
  │                          │                            │
  │ 6. POST /billing/register (authKey)                    │
  ├─────────────────────────▶│                            │
  │                          │ 7. POST /v1/billing/authorizations/issue
  │                          ├───────────────────────────▶│
  │                          │◀───────────────────────────┤
  │                          │ 8. billingKey 저장          │
  │                          │                            │
  │                          │ 9. POST /v1/billing/{billingKey} (첫 결제)
  │                          ├───────────────────────────▶│
  │                          │◀───────────────────────────┤
  │                          │ 10. subscriptions.status='active'
  │◀─────────────────────────┤                            │
  │ 11. 가입 완료 응답        │                            │
  │                          │                            │
  │                          │   (매월 반복)                │
  │                          │ 12. Arq cron → billingKey로 자동 결제
  │                          ├───────────────────────────▶│
  │                          │◀───────────────────────────┤ 13. Webhook PAYMENT.DONE
  │                          │◀───────────────────────────┤
  │                          │ 14. payment_events INSERT, next_billing_at += 1M
```

### 5. Webhook 멱등 처리
- 토스는 재시도 가능: 같은 `event_id` 중복 POST를 가정해야 한다.
- 전략: `payment_events.toss_order_id` UNIQUE 제약 + `INSERT ... ON CONFLICT DO NOTHING`.
- 처리 순서:
  1. 수신 즉시 원본 body + 서명 헤더 로깅.
  2. HMAC SHA-256 서명 검증(`TOSS_WEBHOOK_SECRET`). 실패 시 401.
  3. `event_id` 기반 Redis SETNX(`webhook:processed:{event_id}`, TTL 24h) — 빠른 중복 차단.
  4. DB INSERT(`payment_events`). `ON CONFLICT (toss_order_id) DO NOTHING` 로 이중 방어.
  5. `event_type`에 따라 상태 전이(아래 5절 참조).
  6. 200 OK 반환. 토스는 2xx 외에는 재시도하므로 실패 시 500 반환.

### 6. 구독 상태 전이도
```
          subscribe              charge_success
 (none) ──────────▶ active ───────────────────▶ active  (next_billing_at += 1M)
                     │
                     │ charge_failed (1차)
                     ▼
                past_due ──── retry success ──▶ active
                     │
                     │ retry_fail x3
                     ▼
                suspended ──── 사장 재등록 ──▶ active
                     │
                     │ 30일 방치
                     ▼
                cancelled

    (언제든) cancel 요청 → cancelled_at 기록, cycle 종료까지 active 유지 → cycle 종료 시 cancelled
```
- `past_due`: 재시도 중. 앱 접근은 유지(경고 배너만 표시).
- `suspended`: 3회 재시도 모두 실패. 결제 복구 UI 외 모든 경로 차단.
- `cancelled`: 최종 해지. 재가입은 신규 `subscriptions` row.

### 7. 결제 실패 재시도 전략
- 토스 빌링 API 실패(HTTP 4xx/5xx 또는 응답 내 `code != "DONE"`) 시 `billing_retries` INSERT.
- 초기 `next_retry_at = NOW() + 3 days` (지수 백오프 선택적: `[교차검증 필요]` 3일 고정이 pilot에 적절한지 실측).
- Arq 크론이 매일 새벽 2시 실행 시 `billing_retries WHERE resolved_at IS NULL AND next_retry_at <= NOW()` 처리.
- 성공 시 `resolved_at = NOW()`, 구독 `active` 복귀, `next_billing_at` 재계산.
- 실패 시 `attempt_count += 1`, `next_retry_at += 3 days`. `attempt_count > BILLING_MAX_RETRIES`(기본 3) 도달 시 `resolved_at = NOW()` + 구독 `suspended`.

### 8. 환불 정책
- v1은 no-refund. 해지 시 `cancelled_at`만 기록, `next_billing_at`까지 앱 접근 가능, 이후 `cancelled` 전이.
- pro-rated 환불은 회계 복잡도 대비 가치 낮음(월 ₩19,900–99,900 수준). Post-MVP 재검토.

### 9. 세금계산서
- v1: 자동화 제외. 사업자번호 수집은 `tenants` 테이블(`pivot-backend-multi-tenant`)에서 담당. 관리자가 매월 Hometax에서 수동 발행.
- Post-MVP: 팝빌/바로빌 API 연동 검토.

### 10. 보안
- 카드번호: 위젯이 토스 도메인으로 직접 제출. 우리 서버는 `authKey`(1회용)만 받는다.
- 빌링키: DB에 저장하지만 카드 정보는 포함되지 않음. 분실 시 토스에 재발급 요청 불가(재등록만 가능).
- Webhook 서명 검증: 토스가 전송하는 HMAC 서명을 `TOSS_WEBHOOK_SECRET`로 검증.
- HTTPS 강제(FastAPI 뒤의 리버스 프록시에서 처리).
- `TOSS_SECRET_KEY`는 환경변수 전용, 절대 리포지토리·로그에 기록 금지.

### 11. 스케줄러(Arq)
- `backend/app/billing/scheduler.py`에 2개 크론 태스크:
  - `charge_due_subscriptions`: `0 2 * * *` (매일 02:00 KST). 활성 구독 중 `next_billing_at <= NOW()` 대상 결제.
  - `retry_failed_billings`: `30 2 * * *` (매일 02:30 KST). `billing_retries`의 미해결 건 재시도.
- 기존 `pivot-backend-multi-tenant`에서 Arq worker가 이미 구성되어 있다고 가정. 이 변경은 태스크만 추가.
- 동시성: `[교차검증 필요]` 단일 워커 전제. 다중 워커로 확장 시 `SELECT ... FOR UPDATE SKIP LOCKED`로 경합 방지 필요.

### 12. 관측성
- structlog correlation_id에 `subscription_id` 주입.
- Prometheus 커스텀 메트릭: `billing_charge_total{status}`, `billing_retry_count`, `billing_webhook_received_total{event_type}`, `active_subscriptions_gauge{plan}`.
- Sentry: 빌링 API 호출 실패·Webhook 서명 검증 실패는 즉시 알림.

## Risks / Trade-offs

- [토스페이먼츠 API 장애로 자동결제 실패 급증] → 결제 실패는 항상 `billing_retries` 큐로 수렴, 3회 재시도 후에만 suspended. 장애 시에는 수동 복구 스크립트(`scripts/retry_all_pending.py`) 준비.
- [Webhook이 누락되거나 순서가 뒤바뀐다] → 빌링 API 동기 응답(`POST /v1/billing/{billingKey}`)에서 이미 성공/실패를 받으므로 Webhook은 보조 확인용. 주 소스는 동기 응답, Webhook은 멱등 이중 기록.
- [카드 한도 초과·분실 신고로 연쇄 실패] → 3일 간격 3회 재시도 중 고객에게 이메일/인앱 알림(결제 정보 업데이트 유도). `suspended` 전환 직전 1회 더 유예 안내.
- [플랜 한도(발주 50건/월) 초과 사장의 이탈] → Business 플랜 업그레이드 CTA를 `orders_per_month` 소진 시점에 노출. 한도 초과 시 신규 발주만 차단(기존 기능 유지).
- [Franchise 플랜 도입 시 다중 가맹점 빌링 구조 변경] → 현재 `subscriptions`는 tenant 1:1 매핑. Franchise는 `franchise_memberships` 테이블로 확장 필요(Post-MVP 별도 change).
- [토스 수수료 인상·PG 교체 필요성] → `toss_client.py`를 얇게 유지, `PaymentGateway` 프로토콜(Protocol)로 추상화해 교체 가능 구조. 단 v1은 토스 단일 구현만 제공.
- [Starter 할인가 종료 시 기존 고객 요금 자동 인상 불가(법적 고지 필요)] → `subscriptions.amount_krw`를 가입 시점 가격으로 고정. 요금 인상은 기존 고객에 영향 없음(신규 가입만 정상가).
- [해지 후 재가입 시 빌링키 재사용 가능 여부] → `[교차검증 필요]` 토스 문서 확인. 현재 설계는 해지 시 빌링키 삭제, 재가입 시 재등록 전제.
- [Webhook 서명 검증 우회] → 서명 실패 시 즉시 401 + Sentry 알림. 재시도 로직에서도 검증 필수.
- [테스트 환경에서 실제 결제 발생 위험] → 토스 테스트 키(`test_sk_*`)를 강제하는 환경 검사 추가. 운영 키는 환경변수 whitelist로만 주입.

## Migration Plan

본 변경은 `pivot-backend-multi-tenant` 이후 적용되는 add-on 성격의 신규 모듈이다.

1. 토스페이먼츠 가맹점 가입 + 테스트 키(`test_sk_*`, `test_ck_*`) 발급 + 테스트 Webhook 엔드포인트 등록.
2. `.env` 파일에 `TOSS_SECRET_KEY`, `TOSS_CLIENT_KEY`, `TOSS_WEBHOOK_SECRET` 추가.
3. Alembic 마이그레이션 실행: `subscriptions`, `payment_events`, `billing_retries` 3개 테이블 생성.
4. Arq 워커 재시작 → 새 크론 태스크 등록.
5. Streamlit/Tauri 클라이언트에서 `/api/v1/billing/register` 연동.
6. 토스 테스트 카드로 첫 결제/재시도/해지/Webhook 수신 end-to-end 검증.
7. 운영 키 전환 체크리스트(아래 tasks.md #13) 수행 후 프로덕션 배포.

롤백: Alembic `downgrade -1`로 3개 테이블 DROP. `billing/` 모듈 파일 제거. 빌링키는 우리 쪽에만 있고 토스 측에서도 독립 유지되므로 고객 영향 없음(재가입 필요).

## Open Questions

- 빌링키 분실·유출 시 토스 측 재발급/교체 정책 상세 — `[교차검증 필요]` 토스페이먼츠 빌링 v2 공식 문서 (`https://docs.tosspayments.com/guides/v2/payment-widget/billing`) 확인.
- 3일 간격 3회 재시도가 한국 시장에서 적절한지(타 B2B SaaS 사례) — `[교차검증 필요]` 실측 기반 튜닝, pilot 3개월 후 재검토.
- Webhook 서명 알고리즘·헤더 이름 정확한 명세 — `[교차검증 필요]` 토스페이먼츠 Webhook 문서 확인 후 `webhook.py` 구현.
- 세금계산서 자동 발행 시점 — Post-MVP에서 팝빌/바로빌 중 선택. 월 구독 건수 100건 돌파 시 자동화 착수.
- 사장이 플랜 업그레이드(Starter → Business) 시 즉시 차액 결제 vs 다음 주기부터 인상 — v1은 **다음 주기부터 인상**(즉시 pro-rated 미지원).
- 해지 후 30일 이내 재가입 시 데이터 복구 보장 범위 — tenants 테이블 보존 정책(`pivot-backend-multi-tenant` 소관)과 정합 필요.
- Multi-Shop 플랜의 "다중 사장 계정" 구조 — `pivot-backend-multi-tenant`의 user-tenant 모델과 동기화 필요(본 change에서는 플랜 한도만 정의).
