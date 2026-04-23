# 소매점 조달 SaaS 피벗 리서치 보고서

**Session ID:** research-20260423-pivot-b2b
**Date:** 2026-04-23
**Status:** complete

## Executive Summary

친구용 비공개 최저가 비교 도구를 **소매점 B2B 조달 SaaS**로 피벗하는 타당성과 아키텍처 방향을 조사했다.
현 크롤링 기반 구조(/scraper Mac mini + backend collectors)는 상용화 시 **법적(2017 잡코리아 판례) + 기술적(Akamai 차단) 양면 리스크**가 상존하므로, **클라이언트 로컬 자동화(Chrome Extension 또는 Tauri Desktop 앱)** 방식으로 전환이 필수다.

4개 병렬 조사(Extension MV3 / Tauri 2.0 / 한국 결제 PG / 백엔드 재활용)를 통해 다음 권고를 도출했다:

1. **클라이언트 레이어: Tauri 2.0 Desktop 앱 우선 + Chrome Extension 보조** (B2B 심리적 친화성 + 기술적 안정성)
2. **결제 PG: 토스페이먼츠 빌링 v2 단독 시작**, 매출 확장 시 PortOne 전환
3. **백엔드 재활용: 파싱·랭킹·캐시·모델 50%+ 재사용**, 크롤링 레이어(`collectors/`, `scraper/`) 825줄 폐기
4. **DB 재설계 필요: multi-tenant 스키마** (tenants / users / shops / subscriptions / usage_logs 신규)

## Methodology

### Research Stages

| Stage | Focus | Tier | Status |
|-------|-------|------|--------|
| 1 | Chrome Extension MV3 자동화 타당성 | HIGH | 완료 |
| 2 | Tauri 2.0 Desktop 앱 가능성·비용 | HIGH | 완료 |
| 3 | 한국 결제 PG 비교 (B2B 월구독) | MEDIUM | 완료 |
| 4 | 기존 backend 재활용 범위 분석 | MEDIUM | 완료 |

### Approach

- 병렬 에이전트 4개 동시 조사 (general-purpose + Explore)
- 각 스테이지는 공식 문서 + 실제 구현 사례 참조
- 불확실 사항은 `[교차검증 필요]` 태그로 표시

---

## Key Findings

### Finding 1: Chrome Extension MV3는 기술적으로 가능, 단 쿠팡 봇 탐지·심사가 주 리스크

**Confidence:** HIGH

`chrome.tabs.create({active: false})` + `host_permissions`로 백그라운드 탭 오픈·DOM 파싱은 공식 지원. `manifest.externally_connectable.matches`로 우리 Web App ↔ Extension 메시지 통신 가능.

#### Evidence

- [chrome.tabs API](https://developer.chrome.com/docs/extensions/reference/api/tabs) — 백그라운드 탭 생성 공식 지원
- [externally_connectable manifest](https://developer.chrome.com/docs/extensions/mv3/manifest/externally_connectable/) — Web App 통신 구성
- [MV3 Service Worker lifecycle](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle) — 30초 idle 종료, 5분 상한
- Honey/Capital One Shopping 등 실제 사례: content script → background SW → popup UI 동일 패턴

#### 제약 및 리스크

- **Akamai 탐지 위험**: content script는 isolated world지만 sensor.js는 TLS·Canvas·WebRTC fingerprint 수집. 연속 탭 오픈·빠른 DOM 접근 패턴은 봇 점수 증가 가능. Honey 등은 "현재 방문 탭" 중심이고 **백그라운드 다중 탭 오픈은 더 공격적으로 보일 수 있음**
- **Chrome Web Store 심사 정책**: remote code 금지 + 단일 용도 정책. 자동화는 "unique, high-quality experience" 기준 충족 시 통과 가능하나 장바구니 자동 클릭은 ToS 위반 소지
- **우회 배포 옵션 존재**: Unlisted 배포, Enterprise self-hosting (`ExtensionInstallForcelist` GPO/CBCM) → pilot 단계엔 Unlisted가 가장 현실적

### Finding 2: Tauri 2.0 Desktop 앱도 가능, B2B 친화성 우위

**Confidence:** HIGH

Tauri 2.0의 `WebviewWindow` + `add_child()` API로 multi-webview 운용 + `webview.eval()`로 DOM 자동화 가능. 번들 5-10MB, 메모리 ~50MB로 Electron(120MB+, 80-200MB 번들) 대비 경량.

#### Evidence

- [Tauri 2.0 webview API](https://v2.tauri.app/reference/javascript/api/namespacewebview/) — multi-webview 지원 확인
- [Tauri vs Electron 2026 비교](https://www.pkgpulse.com/blog/electron-vs-tauri-2026) — 번들·메모리 측정 데이터
- [Tauri 2 cookies_for_url](https://docs.rs/tauri/) — 쿠키 jar 조작 Rust 측 가능

#### 핵심 제약

- **WebView는 시스템 Chrome 쿠키와 격리됨** → 사장이 앱에서 별도 로그인 필요 (이건 장점도 됨: 세션 오염 방지)
- **`set_cookie` API 미구현** (issue #11691 OPEN, 2026-04 기준) — POC 단계에서 `webview.eval("document.cookie=...")` 대체경로 검증 필수 `[교차검증 필요]`
- **코드 사이닝 비용**: macOS $99/year (Apple Developer Program 포함) / Windows OV $65-200/year, EV $250-580/year. **2026-02-23 CA/B Forum 룰 변경으로 Windows 인증서 최대 15개월로 단축**
- **업데이터**: `tauri-plugin-updater`는 full-binary (diff 없음). Ed25519 서명키 유출 시 복구 불가 → 별도 안전 보관 필수
- **Electron 대안**: 자동화 도구(puppeteer-core attach) 생태계는 Electron이 성숙. 봇 우회가 코어 경쟁력이면 Electron도 보험안

### Finding 3: 결제 PG는 토스페이먼츠 빌링 v2 단독이 최적

**Confidence:** HIGH

1인 개발자 / 개인사업자 / 월 매출 ₩1-5M 범위에서 토스페이먼츠가 DX·문서·신규자 등록 원스톱 연계로 운영 부담 최소.

#### Evidence

- [토스페이먼츠 자동결제 가이드 v2](https://docs.tosspayments.com/guides/v2/billing) — 빌링 v2 안정 버전
- [토스페이먼츠 PG 수수료](https://www.tosspayments.com/about/fee) — 카드 3.4% + VAT
- [PortOne PG 비교 2026](https://blog.portone.io/opi_pg-comparison2026/) — 업계 벤치마크
- [Stripe KR subscription 문서](https://docs.stripe.com/billing/subscriptions/kr-card) — 한국 개인사업자 계정 개설 불가 확인 `[교차검증 필요]`

#### 권고 조합

| 구독자 수 | 권장 구성 |
|---|---|
| < 100명 / 빠른 출시 | **토스페이먼츠 빌링 v2 단독** |
| 100명+ / 장애·확장 대비 | PortOne V2 + KCP 또는 이니시스 |
| 계좌이체 수요 30%+ | 위 + 페이플(계좌 자동이체) 추가 |

- **초기 비용**: 토스페이먼츠 가입비 22만 + 연 11만 (매출 ₩1M만 돼도 상쇄)
- **Python SDK**: 공식 문서 기반 `httpx.AsyncClient` + Basic Auth + Webhook이면 1-2일 내 FastAPI 연동
- **Stripe는 제외** (한국 개인사업자 계정 개설 불가, 해외 법인 필수)

### Finding 4: 기존 backend 50%+ 재활용 가능, `/collectors` + `/scraper` 825줄 폐기

**Confidence:** HIGH

3,051줄 backend 중 파싱·랭킹·캐시·DB 계층은 multi-tenant 전환 시 거의 그대로 재사용.

#### Evidence

파일 레벨 분류 (Explore agent 분석):

**REUSE (즉시 재활용, 변경 없음)**
- `parsers/regex_parser.py` (223줄) — 옵션 텍스트 수량 파싱
- `parsers/unit_dictionary.py` (86줄) — g/ml/ct/sheet 단위 사전
- `parsers/unit_price.py` (71줄) — 개당가 계산
- `services/ranking_service.py` (44줄) — 개당가 기반 정렬
- `services/shipping_policy.py` (61줄) — 배송비 정책
- `services/cache_service.py` (55줄) — Redis 캐시
- `models/base.py`, `models/option_cache.py`
- `api/v1/router.py`, `api/v1/search.py` — 인증 미들웨어만 추가

**MODIFY (구조 유지, 로직 조정)**
- `parsers/option_parser.py` — 입력 소스 DOM 파싱 결과로 전환
- `parsers/llm_parser.py` — OpenAI 유지, Ollama 이미 제거됨
- `services/quota_service.py` — 플랫폼별 → 테넌트별 할당량
- `services/search_service.py` → **재설계 필요** (크롤링 오케스트레이션 → 테넌트 입력 처리)
- `models/listing.py` — tenant_id 외래키 추가
- `core/config.py` — 테넌트·구독 설정 추가

**DISCARD (폐기)**
- `collectors/` 전체 (825줄) — Playwright·Akamai 우회·원격 스크레이퍼 의존성
- `/scraper/` (별도 디렉토리 전체)
- `collectors/remote_scraper.py`, `naver_detail.py`, `coupang_*`
- `collectors/rate_limiter.py`는 테넌트 quota 관리용으로 이식 가능

#### Multi-tenant DB 신규 스키마

```sql
-- 테넌트·유저·구독
CREATE TABLE tenants (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    plan VARCHAR(32) DEFAULT 'starter',  -- starter/business/multi_shop
    api_quota_monthly INT DEFAULT 10000,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE shops (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT REFERENCES tenants(id),
    name VARCHAR(255),
    business_number VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT REFERENCES tenants(id),
    email VARCHAR(255) NOT NULL,
    auth_provider VARCHAR(32),  -- kakao / naver / local
    role VARCHAR(32) DEFAULT 'owner',
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE subscriptions (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT REFERENCES tenants(id),
    billing_key VARCHAR(255),  -- 토스 빌링키
    plan VARCHAR(32),
    status VARCHAR(32),  -- active/past_due/cancelled
    next_billing_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 기존 테이블에 tenant_id / shop_id 추가
ALTER TABLE listings ADD COLUMN tenant_id BIGINT NOT NULL;
ALTER TABLE listings ADD CONSTRAINT fk_listings_tenant
    FOREIGN KEY(tenant_id) REFERENCES tenants(id);

-- 발주 리스트·리포트
CREATE TABLE procurement_orders (
    id BIGSERIAL PRIMARY KEY,
    shop_id BIGINT REFERENCES shops(id),
    items JSONB,  -- [{name, qty, category}]
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE procurement_results (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT REFERENCES procurement_orders(id),
    platform VARCHAR(32),
    product_data JSONB,
    savings_krw INT,
    fetched_at TIMESTAMP DEFAULT NOW()
);
```

---

## 식별된 독립 기능 영역 (Phase 2 분리 가능성)

리서치 결과, 다음 **4개 독립 영역**으로 분리 가능:

### 영역 A: Backend Multi-Tenant 재설계
- DB 스키마 마이그레이션 (tenants/shops/users/subscriptions/procurement_*)
- 인증 미들웨어 (OAuth: 카카오·네이버 로그인)
- `collectors/` 폐기 + `/scraper/` 삭제
- 기존 파서·랭킹·캐시 모듈 재배치

### 영역 B: Tauri Desktop 클라이언트 (MVP 우선)
- Tauri 2.0 + React/Vue 프론트
- Multi-WebView 쿠팡·네이버 로그인 유지
- DOM 파싱 + 장바구니 자동화
- 백엔드 API 호출 (구독 확인, 리포트 제출)

### 영역 C: Chrome Extension 보조 (선택 구현)
- MV3 manifest + content scripts + background SW
- externally_connectable로 Web App 통신
- Unlisted 배포 (pilot 단계)

### 영역 D: 결제·구독 시스템
- 토스페이먼츠 빌링 v2 연동
- 웹훅 핸들러 (결제 성공·실패·해지)
- 구독 플랜 관리 (Starter/Business/Multi-Shop)

**Phase 2 propose 병렬화 가능**: 영역 A는 먼저 (모든 영역의 기반), 영역 B+C+D는 병렬 진행 가능.

---

## Cross-Validation Results

### 검증된 항목
- Chrome MV3 API 공식 문서 기준 기능 모두 존재 확인
- Tauri 2.0 stable 기능 확인 (2024말 v2 release)
- 토스페이먼츠 빌링 v2 SaaS 실제 사용 사례 (채널톡·Flex 등)
- 기존 backend 파일별 줄 수·기능 실측 완료

### 교차검증 필요 항목
- [ ] Chrome MV3 메시지 크기 실제 상한 (공식 문서 미기재)
- [ ] Tauri `set_cookie` API 2026-04 기준 현황 (issue #11691 OPEN 상태 재확인)
- [ ] Stripe KR 한국 개인사업자 계정 개설 가능 여부 (최근 정책 변경 모니터링)
- [ ] 카카오페이 Direct 실제 수수료율 (공식 가격표 미공개)
- [ ] 쿠팡 Akamai가 Extension content script 환경 탐지하는 실제 사례 수집

---

## Limitations

- 쿠팡 Akamai 탐지 민감도는 실제 운영 전까지 정확한 측정 불가 — POC 필수
- Chrome Web Store 심사 기간·반려 사유는 사례 편차 큼 (2-6주 예상)
- Tauri `set_cookie` 미구현 이슈는 실제 구현 시점에 재확인 필요
- 한국 소상공인 WTP(willingness to pay)는 추정치 — pilot에서 실측 필요
- 법적 리스크는 내가 제시한 게 판례 기반이지만, 실제 Extension 기반 서비스 분쟁 사례는 드물어 판례 적용이 이론 수준 — 정식 사업화 전 법률자문 1회 권장

---

## Recommendations

### 아키텍처 권고

1. **Tauri 2.0 Desktop 앱을 primary 클라이언트로, Chrome Extension은 Phase 2 secondary**로 계획
   - 근거: B2B 소상공인 "프로그램 설치" 문화 친화, 업데이트·라이선스 관리 용이, 쿠팡 봇 탐지 패턴 차별화 가능
   - Chrome Extension은 "가벼운 사장용" 대안 옵션 (나중에 추가)

2. **백엔드는 feature/retail-procurement-pivot에서 multi-tenant 재설계**
   - `/collectors/` + `/scraper/` 삭제
   - 파서·랭킹·캐시 모듈 `app/core/`로 이동
   - 신규: `app/tenancy/` (tenants, shops, users, subscriptions)
   - 신규: `app/procurement/` (발주 리스트 처리, 결과 저장)

3. **결제는 토스페이먼츠 빌링 v2 단독**
   - Phase 1 MVP에선 Starter 플랜만 (월 ₩19,900)
   - 이후 Business/Multi-Shop 플랜 확장

4. **인증은 OAuth 통합** (카카오 + 네이버)
   - 자체 회원가입 제거 (소상공인 가입 장벽 낮춤)
   - `app/auth/` 신규

### 실행 권고

1. **Phase 2 분할**: 영역 A(backend 재설계)를 선행 change로 작성 → 영역 B/D(Tauri 앱 + 결제)를 병렬 change로 작성 → 영역 C(Extension)는 Post-MVP로 보류

2. **Pilot 스코프**:
   - 친구 가게 3-5개
   - Tauri 앱만 배포 (Extension 보류)
   - 쿠팡 + 네이버 스마트스토어 커버
   - 월 ₩19,900 Starter 할인가 (정식 ₩49,900)
   - 3개월 운영 후 지표 기반 사업화 판단

3. **포기해야 하는 것**:
   - 현재 `/scraper` Mac mini 인프라 (서버 크롤링 자체)
   - Streamlit UI (Tauri 앱이 대체)
   - 친구용 "비공개 도구" 포지션 (multi-tenant SaaS로 전환)

---

## Appendix

### Raw Findings Files

개별 에이전트 원본 결과는 이 문서의 "Key Findings" 섹션에 통합됨.

### Session State

- Branch: `feature/retail-procurement-pivot`
- Worktree: `/Users/adminstrator/Desktop/hyungjoo-drb/personal/worktree-feature-retail-procurement-pivot`
- Main 리포트 위치: `.omc/research/research-20260423-pivot-b2b/report.md`
