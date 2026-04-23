## Context

현재 `lowest-price`는 FastAPI 백엔드에 `auth`, `tenancy`, `procurement`, `search`, `quota/cache` 기반을 이미 갖고 있고, 최근 작업은 `tauri-app/`을 사용자-facing 데스크톱 UI로 확장하는 방향이었다. 그러나 신규 수요조사 결과, 소매점 사장 사용자는 설치형 앱이나 비교표 UI보다 카카오톡/SMS로 결과를 받는 흐름을 더 유용하게 인식한다.

따라서 이 설계는 기존 멀티테넌트 백엔드를 유지하되, canonical UX를 “화면 탐색”에서 “알림 수신”으로 바꾼다. `tauri-desktop-mvp`의 WebView, 비교 테이블, 자동 업데이트, 코드사이닝 요구사항은 사용자 제품 범위에서 제외하고 내부 파서 QA/운영 실험 도구로만 남긴다.

카카오 채널 제약도 제품 설계에 직접 반영한다. 조달 결과·견적 완료·발주 상태는 정보성 알림톡으로 설계하고, 가격 리마인더·추천·프로모션성 메시지는 알림톡과 분리해 카카오톡 마케팅 동의 및 채널/브랜드 메시지 조건을 만족할 때만 발송한다. 알림톡/SMS 발송은 공식 딜러 또는 SMS provider와의 계약, 비즈니스 채널 인증, 템플릿 심사, 발신번호/수신거부 정책을 운영 선행조건으로 둔다.

## Goals / Non-Goals

**Goals:**
- 사용자-facing MVP를 카카오 알림톡 + SMS/LMS fallback 기반 Noti-first 조달 결과 알림 서비스로 재정의한다.
- 기존 `auth`, `tenancy`, `procurement_orders`, `quota/cache`, 테스트 인프라를 재사용한다.
- notification recipient, consent, template, delivery, attempt, callback, dead-letter를 테넌트 격리된 도메인으로 추가한다.
- API 요청 경로와 외부 provider 호출을 분리하고, transactional outbox + worker dispatch 패턴으로 발송 안정성을 확보한다.
- 알림톡 정보성 메시지와 마케팅성 채널/브랜드 메시지를 제품 정책과 데이터 모델에서 강제 분리한다.
- README와 기존 OpenSpec 문구를 Noti-first 기준으로 정리할 수 있는 구현 계획을 제공한다.

**Non-Goals:**
- Tauri/React 데스크톱 앱을 사용자-facing 제품으로 완성하지 않는다.
- 비교 테이블 UI, 리포트 대시보드, 설치형 앱 자동 업데이트, 코드사이닝 파이프라인을 구현하지 않는다.
- 자동 장바구니 담기, 브라우저 확장 배포, 일반 SNS/DM 연동은 범위에서 제외한다.
- 카카오 공식 딜러/SMS provider를 특정 벤더로 고정하지 않는다. provider adapter 인터페이스와 설정만 둔다.
- 대규모 마케팅 캠페인, 쿠폰/프로모션 추천 엔진은 범위에서 제외한다.

## Decisions

### 1. 사용자-facing surface는 notification channel로 고정한다

**Decision**: MVP의 1차 사용자 경험은 카카오 알림톡과 SMS/LMS fallback이다. Web/Tauri 화면은 운영자 조회 또는 향후 상세 보기 옵션으로만 둔다.

**Rationale**: 수요조사 결과와 가장 직접적으로 맞고, 기존 백엔드의 조달 결과/리포트 구조를 살리면서 UI 구현·배포·설치·업데이트 비용을 줄일 수 있다.

**Alternatives considered**:
- Tauri UI 유지 + 알림 추가: 기존 작업물을 살리지만 제품 표면이 분산되고 수요조사 결론과 어긋난다.
- Noti-first + 상세 웹 리포트: 유용하지만 MVP 범위가 커진다. 상세 링크는 후속 옵션으로 남긴다.

### 2. `procurement_orders`는 유지하고 notification 도메인은 별도 테이블로 분리한다

**Decision**: `procurement_orders`는 조달 요청/결과 이벤트의 parent로 유지한다. 알림 수신자, 동의, 템플릿, delivery, attempt는 `backend/app/notifications/` 신규 도메인에 별도 모델로 둔다.

**Rationale**: `procurement_results`를 delivery log로 억지 재사용하면 가격 비교 결과와 발송 상태가 섞인다. 이벤트와 delivery attempt를 분리해야 재시도, provider callback, 감사 추적이 가능하다.

**Alternatives considered**:
- `users` 또는 `shops`에 phone 필드만 추가: 단순하지만 수신자별 동의, 채널 상태, 마케팅 opt-in, 실패 이력을 표현하지 못한다.
- `procurement_results`에 notification status 컬럼 추가: 첫 발송은 가능하지만 fallback, 재시도, provider별 message id, callback을 표현하기 어렵다.

### 3. 발송은 transactional outbox + dispatcher worker로 처리한다

**Decision**: 조달 결과 생성/업로드와 `notification_outbox_events` 기록은 같은 DB 트랜잭션에서 수행한다. 실제 Kakao/SMS provider 호출은 dispatcher worker가 `FOR UPDATE SKIP LOCKED` 방식으로 이벤트를 가져와 처리한다.

**Rationale**: 외부 provider 호출을 API 요청 경로에서 수행하면 응답 지연과 부분 실패가 커진다. Outbox는 “DB 상태 변경은 성공했지만 이벤트 발행은 실패”하는 문제를 줄이고, worker 재시작/중복 처리에 대비할 수 있다.

**Alternatives considered**:
- FastAPI `BackgroundTasks`: 작은 same-process 작업에는 충분하지만 프로세스 종료, 배포, 다중 인스턴스에서 내구성이 낮다.
- Redis queue만 사용: 빠르지만 DB 트랜잭션과 원자적으로 묶기 어렵다. MVP는 DB outbox를 source of truth로 둔다.

### 4. Provider adapter는 채널별 공통 인터페이스 뒤에 숨긴다

**Decision**: `NotificationProvider` 인터페이스를 두고 `KakaoAlimtalkProvider`, `KakaoBrandMessageProvider`, `SmsProvider`를 adapter로 구현한다. Provider 결과는 `provider_message_id`, `status`, `raw_response`, `error_code`로 표준화한다.

**Rationale**: 카카오 공식 딜러와 SMS provider는 계약·API·fallback 기능이 다르다. 도메인 서비스가 특정 벤더 API 형태에 묶이면 교체 비용이 커진다.

**Alternatives considered**:
- Kakao API 클라이언트를 service에 직접 주입: 빠르지만 테스트와 벤더 교체가 어렵다.
- provider별 라우터 분리: API 계약이 provider 세부사항에 노출된다.

### 5. 메시지 성격과 동의 모델을 서버에서 강제한다

**Decision**: 템플릿은 `transactional`, `marketing`, `fallback` 같은 message purpose를 가진다. 알림톡은 transactional/informational 템플릿만 허용하고, marketing 목적은 카카오톡 마케팅 동의 및 채널/브랜드 메시지 가능 조건을 요구한다. 광고성 SMS fallback에는 SMS 광고성 동의와 080/수신거부 정책 충족 여부를 요구한다.

**Rationale**: 알림톡에 상품 추천·쿠폰·리뷰 유도·채널 추가 유도 문구가 섞이면 심사 반려 또는 정책 위반이 된다. 제품 레벨에서 분리하지 않으면 운영자가 실수로 잘못된 채널을 사용할 수 있다.

**Alternatives considered**:
- 문구 작성 가이드만 문서화: 사람이 실수할 수 있으므로 서버 검증이 필요하다.
- 모든 메시지를 SMS로 발송: 도달성은 좋지만 비용과 광고성 법규 부담이 커진다.

### 6. 템플릿은 버전 고정과 렌더링 스냅샷을 저장한다

**Decision**: `notification_templates`와 `notification_template_versions`를 분리하고, 각 delivery에는 발송 시점의 rendered title/body/link/fallback body를 저장한다.

**Rationale**: 알림톡 템플릿은 심사 상태와 승인 본문이 중요하다. 나중에 템플릿이 변경돼도 과거 발송 내용과 승인 버전을 감사 가능하게 보존해야 한다.

**Alternatives considered**:
- 템플릿 코드만 저장하고 발송 시 재렌더링: 과거 발송 재현이 불가능하다.
- 하드코딩된 메시지 함수: 심사/버전/반려 사유를 관리하기 어렵다.

### 7. 기존 Tauri 자산은 내부 ingestion/QA 도구로만 유지한다

**Decision**: `tauri-app/`과 `tauri-desktop-mvp` 문서는 제품 요구사항이 아니라 내부 파서 QA/운영 실험 도구로 재분류한다.

**Rationale**: 완전히 삭제하면 기존 파서 실험 자산을 잃지만, 사용자-facing 요구사항으로 남기면 Noti-first 범위와 충돌한다.

**Alternatives considered**:
- 즉시 삭제: 정리가 빠르지만 아직 내부 검증 도구로 쓸 수 있는 코드가 있다.
- 사용자-facing UI로 유지: 제품 방향이 이중화된다.

## Risks / Trade-offs

- **[Kakao template approval delay]** → 운영 선행 과제로 비즈니스 채널 전환, 딜러 계약, 템플릿 심사를 tasks에 포함하고, 승인 전에는 provider fake/stub + SMS dev adapter로 테스트한다.
- **[알림톡 정보성/광고성 오분류]** → 템플릿 purpose와 consent check를 서버에서 강제하고, marketing 문구는 알림톡 provider로 dispatch하지 않는다.
- **[SMS fallback 비용 증가]** → fallback은 transactional 결과 통지에 한정하고, 발송량 quota와 provider-level rate limit을 둔다.
- **[중복 발송]** → `idempotency_key = event_type + order_id + recipient_id + channel + template_version` unique constraint를 둔다.
- **[worker 장애로 발송 지연]** → outbox 상태, attempts, next_retry_at, dead-letter를 저장하고 운영자 조회 API를 제공한다.
- **[provider callback 위조]** → webhook secret/HMAC 검증 또는 provider별 서명 검증을 통과한 callback만 반영한다.
- **[기존 문서와 제품 방향 충돌]** → README와 OpenSpec 영향 문서에 “superseded/product direction only” 문구를 명시한다.

## Migration Plan

1. `backend/app/notifications/` 도메인과 Alembic migration을 추가한다.
2. 기존 auth/tenancy 테스트 fixture를 재사용해 recipient/consent/template/delivery의 tenant isolation을 검증한다.
3. `procurement` service에서 결과 완료 시 outbox event를 생성하되, feature flag로 실제 provider dispatch를 비활성화한 상태로 배포한다.
4. Kakao/SMS provider adapter는 fake provider → sandbox/staging credentials → production credentials 순서로 활성화한다.
5. README와 OpenSpec 문서를 Noti-first 기준으로 갱신하고 Tauri UI를 internal tooling으로 재분류한다.
6. 기존 Tauri 관련 build/test 명령은 제거하지 않고 “internal tooling only”로 문서화한다.

Rollback은 feature flag로 dispatcher를 중지하고, outbox event 생성만 남기는 방식으로 수행한다. DB migration은 additive table 중심으로 설계해 기존 auth/tenancy/procurement API를 깨지 않게 한다.

## Open Questions

- 1차 Kakao/SMS 딜러사는 어디로 둘 것인가? 딜러별 API·fallback 기능이 다르므로 adapter 구현 전 계약 후보를 확정해야 한다.
- 가격 리마인더를 MVP에 포함할 것인가? 포함한다면 카카오톡 마케팅 동의와 채널/브랜드 메시지 조건을 먼저 확보해야 한다.
- recipient의 source of truth를 `users`, `shops`, 별도 `notification_recipients` 중 어디로 둘 것인가? 본 설계는 별도 recipient를 권장한다.
- 상세 결과 링크가 필요한가? MVP에서는 메시지 본문 중심으로 가고, 필요 시 후속 얇은 signed report link를 추가한다.
