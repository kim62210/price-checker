## Why

B2B 소매점 사장을 타겟으로 한 "개당 실가 비교" MVP 는 Chrome Extension 이 아닌 **데스크톱 앱**으로 배포한다. 소상공인 사장 층은 "프로그램 설치" 문화(택배앱·재고앱·키오스크 관리 툴 등)에 이미 친숙하므로 설치 마찰이 낮고, 확장 프로그램 대비 **쿠팡 Akamai 봇 탐지 우회·세션 격리·오프라인 저장**이 구조적으로 유리하다. Electron 대비 번들 5-10MB·메모리 ~50MB(1/10) 수준인 **Tauri 2.0**을 택한다. 법적 근거는 "사장 본인 계정·본인 PC 에서 본인이 조회 · 장바구니 담기"로서 택배앱/발주앱의 구조와 동일하며, 서버 측 크롤링이 아니므로 이용약관 리스크가 낮다.

## What Changes

- 신규 데스크톱 앱 `tauri-app/` 을 Tauri 2.0 + Rust + React + TypeScript 로 신설한다.
- Rust 측 `WebviewWindow::add_child()` API 를 사용해 쿠팡·네이버용 백그라운드 WebView 를 동적으로 생성/파괴한다.
- 사장이 앱 내 WebView 에서 쿠팡·네이버에 직접 로그인해 세션을 앱 data dir(Windows=WebView2, macOS=~/Library/WebKit/<bundleID>)에 영속화한다.
- 발주 리스트 입력 UI(엑셀 붙여넣기, 이전 발주 복제)를 제공하고, "비교 시작" 버튼으로 Rust 측이 품목별 WebView 조회·DOM 파싱 스크립트 주입·결과 수집을 오케스트레이션한다.
- 쿠팡 상세는 JSON-LD, 네이버 스마트스토어 상세는 `__PRELOADED_STATE__` 를 추출해 가격·배송비·옵션 텍스트를 파싱한다.
- 결과를 **개당 실가(`(옵션가 + 배송비) / 실수량`)** 오름차순 비교 테이블로 표시한다. "장바구니 담기" 는 MVP 에서는 수동 복사 지원만, 자동 담기는 옵션 기능(후속).
- 백엔드(영역 A FastAPI) REST API 와 JWT 인증으로 연동해 **구독 상태·발주 제출·파싱 결과 업로드·누적 절약액 리포트**를 교환한다.
- **human-like delay**(요청 사이 200-800ms 랜덤 sleep) 주입으로 Akamai 봇 탐지 완화.
- `tauri-plugin-updater` + Ed25519 서명 기반 자동 업데이트 + `tauri-plugin-sql`(SQLite) 기반 오프라인 저장.
- macOS(Apple Developer ID + notarization) / Windows(OV code signing, 2026-02-23 CA/B 룰 기준 15개월 인증서) 코드 사이닝 파이프라인 구축.
- 기존 `backend/ui/streamlit_app.py` 는 내부 QA 툴로만 유지하고, 외부 배포 UI 는 본 Tauri 앱으로 대체한다.

## Capabilities

### New Capabilities
- `webview-manager`: Rust 측 다중 WebView 생성/파괴, 탭별 쿠키·세션 격리, `webview.eval()` 로 DOM 파싱 스크립트 주입·결과 회수.
- `dom-parsers`: 쿠팡 상세(JSON-LD) / 네이버 스마트스토어 상세(`__PRELOADED_STATE__`) 파싱 스크립트(TypeScript). Rust 에서 주입·실행·JSON 회수.
- `procurement-workflow`: 발주 리스트 입력 → WebView 병렬 조회 → 파싱 → 개당 실가 계산 → 비교 테이블 표시 → 백엔드 리포트 제출 의 프론트엔드·Rust 합동 플로우.
- `auto-updater`: `tauri-plugin-updater` 기반 자동 업데이트 채널 + Ed25519 서명 + 업데이트 서버(GitHub Releases 또는 자체 CDN) 연동.

### Modified Capabilities
- (없음 — 본 change 는 데스크톱 앱 신규 추가. 백엔드 API 계약은 영역 A change 에서 정의.)

## Impact

- **신규 코드**: `tauri-app/` 전체 (`src-tauri/` Rust, `src/` React+TS, `content-scripts/` 파싱 스크립트)
- **의존성 (Rust/Cargo)**: `tauri@2`, `tauri-plugin-updater@2`, `tauri-plugin-sql@2`, `tauri-plugin-http@2`, `reqwest`, `serde`, `serde_json`, `tokio`, `rand`, `tracing` [교차검증 필요 — 각 플러그인 최신 버전 공식 문서 확인]
- **의존성 (npm/pnpm)**: `react@18`, `react-dom@18`, `typescript@5`, `@tauri-apps/api@2`, `@tauri-apps/plugin-updater`, `@tauri-apps/plugin-sql`, `vite`, `zod` (백엔드 응답 검증)
- **외부 API**: 영역 A 백엔드(`POST /api/v1/auth/kakao`, `GET /api/v1/shops/me`, `POST /api/v1/procurement/orders`, `POST /api/v1/procurement/results`, `GET /api/v1/procurement/reports`, `GET /api/v1/subscription/status`)
- **WebView 환경**: Windows=WebView2(Chromium), macOS=WKWebView(Safari 엔진)
- **코드 사이닝 비용**: Apple Developer Program $99/year, Windows OV $65-200/year [교차검증 필요 — 2026년 CA 상품별 최신가]
- **배포**: GitHub Releases(MVP pilot) 또는 자체 CDN(프로덕션). `.dmg`(macOS) / `.msi`(Windows) 형태로 사장에게 개별 전달.
- **대체**: 기존 `backend/ui/streamlit_app.py` 는 내부 개발용으로만 유지, 사용자 대면 UI 는 본 Tauri 앱으로 대체.
- **파일**: `openspec/changes/tauri-desktop-mvp/` 아래 4개 artifact + `specs/` 4개 capability, 프로젝트 루트에 `tauri-app/` 신설.
- **법적 제약**: 사장 본인 계정·본인 PC 에서 본인이 조회하는 구조로 한정. 서버 측 크롤링·대량 수집·공개 API 는 본 change 범위 외.

## Open Questions / Pre-implementation Checks

- [교차검증 필요] Tauri 2.x 에서 `WebviewWindow::add_child()` 시그니처와 다중 WebView 생성·제거 패턴의 **공식 예제**(issue/discussion 또는 공식 docs) 를 착수 전 재확인.
- [교차검증 필요] `set_cookie` API 미구현(GitHub issue #11691 OPEN) 상태에서, WebView2/WKWebView 의 `webview.eval("document.cookie=...")` 대체 경로가 HttpOnly 쿠키에 대해 어떤 제약을 가지는지 POC 로 검증.
- [교차검증 필요] macOS notarization 최신 절차(`notarytool submit` + `stapler staple`) 및 Windows OV 코드 사이닝 인증서 공급자(DigiCert, Sectigo, SSL.com) 가격/절차 2026-04 시점 최신화.
- 자동 담기 기능은 MVP 에서 옵션(플래그)로만 두고 pilot 피드백 후 판단. 초기 릴리즈에는 수동 복사만 지원.
