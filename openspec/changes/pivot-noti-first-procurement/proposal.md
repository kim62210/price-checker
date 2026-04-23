## Why

신규 수요조사 결과, 소매점 사장 사용자는 별도 데스크톱 UI에 접속해 비교표를 탐색하기보다 카카오톡/SMS로 조달 결과와 재확인 필요 상태를 즉시 받아보는 방식에서 더 큰 효용을 느낀다. 따라서 `lowest-price`의 canonical product surface를 Tauri/React UI에서 **Noti-first 조달 결과 알림 서비스**로 전환해, 기존 멀티테넌트 백엔드를 유지하면서 사용자-facing UX를 알림 채널 중심으로 재정의한다.

이 변경은 `tauri-desktop-mvp`, `add-lowest-price-mvp`, `IMPLEMENTATION_PLAN.md`의 제품 방향을 supersede한다. 기존 `tauri-app/` 자산은 사용자-facing 제품이 아니라 내부 파서 QA, 운영자 디버깅, 향후 optional ingestion 실험용 도구로만 취급한다.

## What Changes

- **BREAKING**: Tauri/React 데스크톱 앱은 더 이상 1차 사용자-facing 제품 표면이 아니다. 비교 테이블, 리포트 대시보드, 설치형 앱 업데이트, WebView 로그인 UX는 MVP 범위에서 제거하거나 내부 도구로 강등한다.
- 기존 `auth`, `tenancy`, `procurement_orders`, `quota/cache` 기반은 유지하고, 조달 결과 이벤트를 알림 발송으로 이어주는 notification 도메인을 신규 추가한다.
- 조달 결과·견적 완료·발주 상태 같은 거래성/필수 고지는 카카오 알림톡을 1차 채널로 사용하고, 미도달/실패 시 SMS/LMS fallback을 수행한다.
- 가격 리마인더·프로모션성 메시지는 알림톡과 분리하고, 명시적 카카오톡 마케팅 동의 및 채널/브랜드 메시지 대상 조건을 만족할 때만 발송한다.
- 알림톡 템플릿 승인, 템플릿 버전, 렌더링 스냅샷, 발송 로그, provider callback, 재시도, dead-letter를 제품 기능으로 관리한다.
- 발송은 API 요청 경로에서 직접 수행하지 않고, 같은 DB 트랜잭션에 outbox event를 기록한 뒤 별도 worker/dispatcher가 Kakao/SMS adapter를 호출한다.
- README와 기존 OpenSpec 문구는 “Tauri/Web UI”가 아니라 “notification-first workflow”를 기준으로 갱신한다.

## Capabilities

### New Capabilities
- `notification-consents`: 테넌트별 수신자 연락처, 거래성 안내 근거, 카카오톡 마케팅 동의, SMS 광고성 동의, 야간 광고성 동의 상태를 관리한다.
- `notification-templates`: 카카오 알림톡/브랜드 메시지/SMS fallback 템플릿 카탈로그, 버전, 심사 상태, 렌더링 스냅샷 정책을 관리한다.
- `notification-delivery`: 조달 결과 이벤트를 수신자·채널·템플릿별 delivery로 전개하고, provider message id, 발송 상태, 실패 사유, callback 상태를 추적한다.
- `notification-dispatch`: transactional outbox, worker dequeue, provider adapter, retry/backoff, idempotency, dead-letter 처리를 담당한다.

### Modified Capabilities
- `procurement-orders`: 발주 주문은 사용자 입력 UI의 결과물이 아니라 알림 대상이 되는 조달 요청/결과 이벤트의 기준 엔티티로 재정의한다.
- `procurement-results`: 업로드된 가격 비교 결과는 화면 렌더링용 테이블이 아니라 알림 payload와 요약 리포트의 근거 데이터로 사용한다.
- `auth-oauth`: 카카오/네이버 OAuth는 데스크톱 앱 로그인용이 아니라 알림 설정·테넌트 관리·운영자 인증의 기반으로 유지한다.
- `tenancy`: 테넌트/매장/사용자 격리를 notification recipient, consent, delivery log까지 확장한다.
- `search-api`: 사용자-facing 검색 UI의 직접 응답보다 알림 payload 생성과 내부 운영 조회를 지원하는 보조 API로 재분류한다.

## Impact

- **Affected backend modules**: `backend/app/procurement/`, `backend/app/tenancy/`, `backend/app/auth/`, `backend/app/services/quota_service.py`, `backend/app/services/cache_service.py`, `backend/app/core/config.py`, `backend/app/api/v1/router.py`, `backend/app/db/migrations/`.
- **New backend module**: `backend/app/notifications/` with models, schemas, service, dispatcher, provider adapters, router, and tests.
- **New persistence**: notification recipients/consents, templates/template versions, outbox events, deliveries, delivery attempts, provider callbacks, dead letters.
- **External systems**: Kakao Alimtalk/Brand Message dealer API, SMS/LMS provider, provider callback endpoint, business channel/template approval operations.
- **Configuration**: Kakao BizMessage provider credentials, sender profile/channel identifiers, SMS sender number/provider credentials, webhook secret, retry limits, notification quota settings.
- **Docs/OpenSpec**: `README.md`, `IMPLEMENTATION_PLAN.md`, `openspec/changes/tauri-desktop-mvp/*`, `openspec/changes/pivot-backend-multi-tenant/*`, and `openspec/changes/toss-payments-billing/*` require wording updates to remove Tauri/Web UI as the canonical UX.
- **Deferred/non-goals**: full Tauri/React user UI, comparison dashboard, auto-updater, automatic cart insertion, browser extension distribution, and generic SNS/DM integrations.
