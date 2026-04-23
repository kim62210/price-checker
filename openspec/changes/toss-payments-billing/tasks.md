## 1. 토스페이먼츠 가맹점 가입·테스트 키

- [ ] 1.1 토스페이먼츠 가맹점 신청 (개인사업자 원스톱 등록 활용)
- [ ] 1.2 테스트용 `TOSS_SECRET_KEY`(`test_sk_*`), `TOSS_CLIENT_KEY`(`test_ck_*`) 발급
- [ ] 1.3 테스트 Webhook 엔드포인트 등록 (`https://staging.example.com/api/v1/billing/webhook`)
- [ ] 1.4 `TOSS_WEBHOOK_SECRET` 생성·저장
- [ ] 1.5 `.env.example`에 빌링 관련 환경변수 추가 (`TOSS_SECRET_KEY`, `TOSS_CLIENT_KEY`, `TOSS_WEBHOOK_SECRET`, `BILLING_RETRY_INTERVAL_DAYS`, `BILLING_MAX_RETRIES`, `BILLING_SCHEDULER_CRON`, `PILOT_MODE`, `BILLING_KEY_ENCRYPTION`)

## 2. billing 모듈 초기화

- [ ] 2.1 `backend/app/billing/__init__.py` 생성
- [ ] 2.2 `backend/app/core/config.py`에 `TossPaymentsSettings` 중첩 설정 추가 (pydantic-settings)
- [ ] 2.3 `backend/app/billing/` 하위 파일 스캐폴드 (models, toss_client, service, webhook, scheduler, router, plans)

## 3. DB 스키마·Alembic migration

- [ ] 3.1 `backend/app/billing/models.py` — `Subscription`, `PaymentEvent`, `BillingRetry` SQLAlchemy 모델 (async 세션 호환)
- [ ] 3.2 `subscriptions` UNIQUE 부분 인덱스 (`WHERE status IN ('active','past_due')`) 제약 추가
- [ ] 3.3 `payment_events.toss_order_id` UNIQUE 제약 추가 (멱등성)
- [ ] 3.4 `billing_retries` 부분 인덱스 (`WHERE resolved_at IS NULL`) 추가
- [ ] 3.5 Alembic 리비전 생성·검토·적용

## 4. 토스페이먼츠 API 래퍼 (`toss_client.py`)

- [ ] 4.1 `TossPaymentsClient` 클래스 — `httpx.AsyncClient` + Basic Auth(secret_key + `:`)
- [ ] 4.2 `issue_billing_key(auth_key, customer_key)` — `POST /v1/billing/authorizations/issue`
- [ ] 4.3 `charge(billing_key, amount, order_id, order_name, customer_key)` — `POST /v1/billing/{billingKey}`
- [ ] 4.4 `cancel_billing_key(billing_key)` — 빌링키 해지 호출 `[교차검증 필요]` 공식 엔드포인트 확인
- [ ] 4.5 tenacity 재시도(지수 백오프, 최대 3회, 429/5xx만)
- [ ] 4.6 타임아웃 설정 (`connect=3, read=10, write=3, pool=5`)
- [ ] 4.7 테스트 환경 가드 — 운영 키(`live_sk_*`)가 `ENV != production` 에서 주입되면 즉시 예외

## 5. 구독 비즈니스 로직 (`service.py`)

- [ ] 5.1 `SubscriptionService.create(tenant_id, plan_code, auth_key, customer_key)` — 빌링키 발급 → 첫 결제 → `subscriptions` INSERT
- [ ] 5.2 `SubscriptionService.cancel(subscription_id)` — `cancelled_at` 기록, cycle 종료까지 active 유지
- [ ] 5.3 `SubscriptionService.get_status(tenant_id)` — 현재 활성 구독 조회
- [ ] 5.4 `SubscriptionService.list_invoices(tenant_id, limit, offset)` — `payment_events` 기반 결제 내역
- [ ] 5.5 `SubscriptionService.apply_plan_change(subscription_id, new_plan_code)` — 다음 주기부터 반영 (v1 즉시 반영 미지원)
- [ ] 5.6 상태 전이 검증 헬퍼 (`_assert_transition_allowed`)
- [ ] 5.7 `PLAN_LIMITS` 조회 헬퍼 (발주 건수·가게 수 한도)

## 6. Webhook 처리 (`webhook.py`)

- [ ] 6.1 `verify_signature(raw_body, signature_header)` — HMAC SHA-256, `TOSS_WEBHOOK_SECRET` 기반 `[교차검증 필요]` 토스 Webhook 서명 헤더 이름·알고리즘 공식 확인
- [ ] 6.2 `process_payment_done(payload)` — `payment_events` INSERT(`ON CONFLICT DO NOTHING`), `next_billing_at` 갱신
- [ ] 6.3 `process_payment_failed(payload)` — `billing_retries` 큐잉, 구독 상태 `past_due` 전이
- [ ] 6.4 `process_billing_canceled(payload)` — 구독 `cancelled` 처리
- [ ] 6.5 Redis SETNX(`webhook:processed:{event_id}`, TTL 24h)로 빠른 중복 차단
- [ ] 6.6 서명 실패 시 401 + Sentry 알림

## 7. 정기결제 Arq 태스크 (`scheduler.py`)

- [ ] 7.1 `charge_due_subscriptions` 크론 (`0 2 * * *` KST) — `SELECT ... WHERE next_billing_at <= NOW() AND status = 'active' FOR UPDATE SKIP LOCKED`
- [ ] 7.2 각 구독에 대해 `TossPaymentsClient.charge()` 호출
- [ ] 7.3 성공 시 `next_billing_at += 1 month`, `payment_events` INSERT
- [ ] 7.4 실패 시 `billing_retries` INSERT + 상태 `past_due` 전이
- [ ] 7.5 처리 통계 로깅 (성공/실패 건수)

## 8. 재시도 Arq 태스크 (`scheduler.py`)

- [ ] 8.1 `retry_failed_billings` 크론 (`30 2 * * *` KST) — `billing_retries WHERE resolved_at IS NULL AND next_retry_at <= NOW()`
- [ ] 8.2 각 건에 대해 `TossPaymentsClient.charge()` 재호출
- [ ] 8.3 성공 시 `resolved_at` 기록, 구독 `active` 복귀
- [ ] 8.4 실패 시 `attempt_count += 1`, `next_retry_at += BILLING_RETRY_INTERVAL_DAYS`
- [ ] 8.5 `attempt_count > BILLING_MAX_RETRIES` 시 `resolved_at` 기록 + 구독 `suspended`
- [ ] 8.6 suspended 전환 시 사장에게 이메일/알림 (별도 notification 모듈 위임)

## 9. FastAPI 엔드포인트 (`router.py`)

- [ ] 9.1 `POST /api/v1/billing/register` — authKey 수신, 빌링키 발급만 수행
- [ ] 9.2 `POST /api/v1/billing/subscribe` — 플랜 선택 + 빌링키 사용해 구독 생성·첫 결제
- [ ] 9.3 `POST /api/v1/billing/cancel` — 구독 해지 요청
- [ ] 9.4 `GET /api/v1/billing/status` — 현재 구독 상태·다음 결제일 조회
- [ ] 9.5 `POST /api/v1/billing/webhook` — 토스 Webhook 수신 엔드포인트 (서명 검증 → 라우팅)
- [ ] 9.6 `GET /api/v1/billing/invoices?limit=&offset=` — 결제 내역 페이지네이션
- [ ] 9.7 모든 라우트에 `response_model` 명시, `status.HTTP_*` 상수 사용
- [ ] 9.8 `backend/app/billing/schemas.py` — Pydantic v2 요청/응답 스키마
- [ ] 9.9 `backend/app/main.py`에 billing 라우터 등록

## 10. 플랜 상수 정의 (`plans.py`)

- [ ] 10.1 `Plan` dataclass 정의 (code, price_krw, pilot_price_krw, orders_per_month, max_shops, enabled)
- [ ] 10.2 `PLANS` 딕셔너리 선언 (starter / business / multi_shop / franchise)
- [ ] 10.3 `get_plan_price(plan_code)` 헬퍼 — `settings.PILOT_MODE` 분기
- [ ] 10.4 Franchise는 `enabled=False` 고정 (Post-MVP)
- [ ] 10.5 `validate_plan_code(code)` 검증 헬퍼

## 11. 구독 상태 미들웨어

- [ ] 11.1 `backend/app/core/middleware.py`에 `SubscriptionStatusMiddleware` 추가
- [ ] 11.2 요청 tenant의 구독 상태 조회 (Redis 캐시 30초 TTL)
- [ ] 11.3 `suspended` 테넌트는 `/api/v1/billing/*` 외 모든 경로 403 차단
- [ ] 11.4 `past_due`는 응답 헤더에 `X-Subscription-Warning: past_due` 추가 (경고만)
- [ ] 11.5 `cancelled`(cycle 종료 후)는 `suspended`와 동일 차단
- [ ] 11.6 플랜 한도 체크 — 발주 생성 시 `orders_per_month` 소진 여부 검증(별도 발주 모듈 연계)

## 12. 테스트

- [ ] 12.1 `backend/tests/billing/test_toss_client.py` — `respx`로 토스 API 모킹, 재시도·타임아웃 검증
- [ ] 12.2 `backend/tests/billing/test_service.py` — 구독 생성·해지·상태 전이 단위 테스트
- [ ] 12.3 `backend/tests/billing/test_webhook.py` — 서명 검증(유효/무효), 멱등성(중복 event_id), 각 event_type 처리
- [ ] 12.4 `backend/tests/billing/test_scheduler.py` — `charge_due_subscriptions`·`retry_failed_billings` Arq 태스크 통합 테스트
- [ ] 12.5 `backend/tests/billing/test_router.py` — 모든 엔드포인트 AsyncClient 통합 테스트 (인증 포함)
- [ ] 12.6 `backend/tests/billing/test_plans.py` — 플랜 상수·pilot 가격 분기·Franchise 비활성화
- [ ] 12.7 `backend/tests/billing/test_middleware.py` — suspended/past_due/cancelled 각 시나리오
- [ ] 12.8 테스트용 팩토리 (`tests/factories/billing_factory.py`) — Subscription·PaymentEvent 더미 생성
- [ ] 12.9 커버리지 80% 이상 유지 (`pytest --cov=backend/app/billing`)

## 13. 프로덕션 키 전환 체크리스트

- [ ] 13.1 운영 가맹점 심사 완료·운영 키(`live_sk_*`, `live_ck_*`) 발급 확인
- [ ] 13.2 운영 Webhook URL 토스 콘솔에 등록 (`https://api.example.com/api/v1/billing/webhook`)
- [ ] 13.3 운영 `TOSS_WEBHOOK_SECRET` 재생성·환경변수 주입
- [ ] 13.4 `ENV=production` + `live_sk_*` 조합에서만 실제 결제 허용하는 가드 검증
- [ ] 13.5 테스트 카드로 production 환경 smoke test (₩100 결제 후 즉시 환불)
- [ ] 13.6 Sentry·Prometheus 대시보드에 billing 메트릭 패널 추가
- [ ] 13.7 `docs/billing-operations.md` 작성 — 장애 대응·수동 재시도·고객문의 응대 절차 `[교차검증 필요]` 팀 내부 운영 문서화 형식 합의 후 작성
- [ ] 13.8 개인정보처리방침·이용약관에 PG 사용 명시 (토스페이먼츠·SAQ-A)
- [ ] 13.9 롤백 절차 리허설 (`alembic downgrade -1` + billing 모듈 disable)
