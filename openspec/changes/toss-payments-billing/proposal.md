## Why

소매점 발주 도구를 B2B SaaS로 피벗하면서 **월 구독 과금**이 수익 모델의 핵심이 된다. 한국 시장에 가장 적합한 PG는 **토스페이먼츠 빌링 v2**로 선정: 카드 3.4% + VAT·계좌이체 2.0%(최소 ₩200)·가입비 ₩22만 + 연 ₩11만의 경쟁적 수수료, 업계 최고 수준의 문서 품질, Webhook 멱등키 지원, 개인사업자 신규 등록 원스톱 연계, 채널톡·Flex·당근 등 다수 B2B SaaS가 이미 채택해 레퍼런스가 풍부하다. `httpx.AsyncClient` + Basic Auth + Webhook 핸들러 패턴으로 FastAPI 연동은 1-2일 규모로 추정되며, 카드번호는 서버에 절대 저장하지 않고 빌링키만 보관해 **SAQ-A 수준**으로 PCI DSS 부담을 최소화한다.

## What Changes

- `billing` 도메인 모듈 신규: `models.py`, `toss_client.py`, `service.py`, `webhook.py`, `scheduler.py`, `router.py`, `plans.py` 구성.
- 신규 테이블 3종: `subscriptions`(테넌트별 활성 구독·빌링키·다음 결제일), `payment_events`(결제 성공/실패/구독/해지 이력), `billing_retries`(재시도 큐).
- Starter ₩19,900 / Business ₩49,900 / Multi-Shop ₩99,900 3-티어 플랜을 `plans.py` 상수로 정의한다. Franchise ₩300,000+ 는 Post-MVP.
- 초기 pilot 한정 Starter 할인가 ₩19,900(정식 출시 시 ₩49,900) 쿠폰 전략을 `plans.py`에 명시한다.
- 결제 플로우: 플랜 선택 → 토스 카드등록 위젯 → 빌링키 발급 → 즉시 첫 결제 → 매월 동일 일자 자동 결제 → 실패 시 3일 간격 3회 재시도 → 3회 실패 시 `suspended`.
- Webhook 이벤트 3종 처리: `PAYMENT.DONE`, `PAYMENT.FAILED`, `BILLING.CANCELED`. `event_id` 기반 멱등 처리로 중복 수신 방어.
- 백엔드 API 6종: `POST /api/v1/billing/register`, `POST /api/v1/billing/subscribe`, `POST /api/v1/billing/cancel`, `GET /api/v1/billing/status`, `POST /api/v1/billing/webhook`, `GET /api/v1/billing/invoices`.
- Arq 스케줄러: 매일 새벽 2시(KST) 실행, `next_billing_at <= NOW() AND status = 'active'` 대상에게 빌링 API 호출. 성공 시 `next_billing_at += 1 month`, 실패 시 `billing_retries` 큐잉.
- 구독 상태 미들웨어: `suspended` 테넌트는 신규 조달/알림 dispatch를 차단하고, 결제 복구 안내는 Noti-first notification channel로 전달한다.
- 해지 시 현재 billing cycle 종료까지 활성 유지(즉시 환불 없음).

## Capabilities

### New Capabilities
- `subscription-lifecycle`: 플랜 선택·빌링키 발급·첫 결제·매월 자동 결제·해지 요청·상태 전이(`active → past_due → suspended → cancelled`)를 관리한다.
- `toss-payments-integration`: 토스페이먼츠 빌링 v2 API(`POST /v1/billing/{billingKey}`, 카드등록 위젯, 빌링키 해지)를 `httpx.AsyncClient` + Basic Auth로 래핑한다.
- `billing-webhook`: 토스 Webhook 수신 시 HMAC 서명 검증 + `event_id` 기반 멱등 처리로 `PAYMENT.DONE`/`PAYMENT.FAILED`/`BILLING.CANCELED`를 안전하게 반영한다.
- `scheduled-charging`: Arq 크론으로 매일 정기결제 배치와 재시도 배치를 실행한다.

### Modified Capabilities
- (없음 — `pivot-backend-multi-tenant`에서 정의된 `tenants` 테이블을 FK로 참조하지만 기존 capability는 변경하지 않는다)

## Impact

- **선행 의존**: `pivot-backend-multi-tenant` (tenants·auth 구조 선행 필요). `pivot-noti-first-procurement` 이후 결제 복구·실패 커뮤니케이션은 UI 연동이 아니라 notification channel 연동을 기준으로 한다.
- **신규 코드**: `backend/app/billing/` 전체 패키지(models, toss_client, service, webhook, scheduler, router, plans), 구독 상태 차단 미들웨어(`backend/app/core/middleware.py` 갱신).
- **신규 테이블**: `subscriptions`, `payment_events`, `billing_retries` (Alembic 마이그레이션 1건).
- **의존성**: `httpx[http2]`(기존), `arq`(기존), `redis`(기존). 신규 패키지 추가 없음.
- **환경변수**: `TOSS_SECRET_KEY`, `TOSS_CLIENT_KEY`, `TOSS_WEBHOOK_SECRET`, `BILLING_RETRY_INTERVAL_DAYS`(기본 3), `BILLING_MAX_RETRIES`(기본 3), `BILLING_SCHEDULER_CRON`(기본 `0 2 * * *`).
- **외부 서비스**: 토스페이먼츠 가맹점 가입 + 테스트/운영 키 발급. 개인사업자 등록 원스톱 연계 가능.
- **컴플라이언스**: 카드번호 서버 미저장(빌링키만), SAQ-A 수준 PCI DSS. 개인정보(이메일·사업자번호) 애플리케이션 레벨 암호화(`pivot-backend-multi-tenant`에서 정의).
- **세금계산서**: v1에서는 자동화 제외(수동 발행). 사업자 고객이 요청 시 관리자가 별도 처리.
- **환불 정책**: v1에서는 no-refund(pro-rated 미지원). 해지 시 현재 billing cycle 종료까지 사용 가능.
- **파일**: `openspec/changes/toss-payments-billing/` 아래 4개 아티팩트(proposal/design/tasks + specs/ 4개).
