## Context

- 타겟 사용자: B2B 소매점 사장(편의점·무인매장·소형 슈퍼 등) 5-20명 규모의 pilot.
- 소상공인 사장 층은 "프로그램 설치" 문화(택배앱, POS 관리, 재고앱)에 익숙해 설치 마찰이 낮다.
- 기존 접근 대비 데스크톱 앱의 장점:
  - **Chrome Extension 대비**: 설치 친숙도 ↑, 쿠팡 Akamai 탐지 패턴 차별화 가능(extension DOM hook 탐지 회피), 확장프로그램 정책(Manifest V3 하의 `webRequest` 제약) 회피.
  - **Electron 대비**: 번들 5-10MB(Electron 80-150MB 대비 1/10), 메모리 ~50MB, 시스템 WebView 재사용.
  - **서버 측 크롤링 대비**: "사장 본인 계정·본인 PC" 라 법적 리스크가 택배앱/발주앱과 동급으로 낮음.
- Tauri 2.0 의 multi-webview 기능은 `WebviewWindow::add_child()` API 로 한 창 안에 여러 webview 를 동적 추가·제거할 수 있다 [교차검증 필요 — 착수 전 공식 docs·issue 예제 재확인].
- WebView 환경: Windows=WebView2(Chromium), macOS=WKWebView(WebKit). 쿠키/세션은 앱별 data dir 에 영속화되어 시스템 브라우저와 격리된다. 이는 "본인 로그인 세션이 앱에만 격리되어 있음" 을 사장에게 어필할 수 있는 UX 포인트.

## Goals / Non-Goals

**Goals:**
- 사장이 앱 실행 → 내장 WebView 로 쿠팡·네이버에 로그인 → 발주 리스트 입력 → "비교 시작" 한 번으로 개당 실가 기준 정렬된 비교 테이블을 확인할 수 있다.
- WebView 자동화는 **human-like 리듬**(랜덤 delay, UA 동일, 탭 전환 최소화)으로 수행해 Akamai 탐지를 완화한다.
- 백엔드(영역 A) 와 JWT + HTTPS 로 연동해 구독 상태 확인, 발주/결과 제출, 누적 절약액 리포트를 교환한다.
- 자동 업데이트와 코드 사이닝(macOS/Windows)을 MVP pilot 단계부터 갖춘다.
- 오프라인 저장(SQLite)으로 인터넷 단절 시에도 최근 발주·비교 결과를 볼 수 있다.

**Non-Goals:**
- 대량 가격 수집·실시간 모니터링 등 크롤링 서비스 기능(본 앱은 "사장 1인의 발주 도구").
- 쿠팡/네이버 외 플랫폼(11번가, G마켓, 옥션, SSG 등) — post-MVP.
- 자동 결제(결제는 사장이 직접 수행).
- 모바일(iOS/Android) 앱 — post-MVP, Tauri 2.0 mobile 도입 시 검토.
- Linux 바이너리 배포(MVP 는 macOS + Windows 만).
- 사장 간 데이터 공유·협업(멀티 사장 조직 모드) — post-MVP.

## Decisions

### 1. 프레임워크: Tauri 2.0
- Rust 백엔드 + 시스템 WebView(Windows=WebView2, macOS=WKWebView).
- 번들 5-10MB, 메모리 ~50MB(Electron 의 1/10).
- 대안 비교:
  - Electron: 번들/메모리 부담, 하지만 단일 Chromium 으로 모든 OS 일관성. 본 앱은 Tauri 의 크기·성능 이점이 더 중요.
  - Neutralino.js / Webview(Go) / Wails(Go): 생태계·플러그인 성숙도 낮음, 자동 업데이트·코드 사이닝 지원 약함.
  - PWA: 쿠키·세션 격리와 다중 webview 동시 자동화가 불가.

### 2. 프론트엔드: React 18 + TypeScript 5 + Vite
- `App.tsx` 를 중심으로 발주 입력·비교 테이블·리포트·로그인 안내 컴포넌트 구성.
- 백엔드 응답 스키마는 `zod` 로 런타임 검증(영역 A 와 계약 깨졌을 때 즉시 감지).
- 상태 관리는 React Context + `useReducer` 로 시작(Zustand/Redux 는 규모 커지면 도입).

### 3. 디렉토리 구조
```
tauri-app/
  src-tauri/
    src/
      main.rs                 (엔트리, 플러그인 등록, 메인 창 생성)
      webview_manager.rs      (WebView 풀, 탭 생성·파괴, eval)
      parser_bridge.rs        (content-scripts 번들 주입, 결과 회수, JSON 역직렬화)
      auth.rs                 (JWT 보관/갱신, keyring 또는 tauri-plugin-sql)
      api_client.rs           (reqwest 기반 백엔드 REST 호출)
      commands.rs             (#[tauri::command] 모음, 프론트↔Rust 브릿지)
      error.rs                (thiserror 기반 에러 타입)
      config.rs               (백엔드 URL, 플랫폼 타임아웃 등)
    Cargo.toml
    tauri.conf.json           (번들 설정, updater endpoint, permissions)
    capabilities/default.json (Tauri 2.0 capability 설정)
    icons/
    build.rs
  src/                        (React 프론트)
    App.tsx
    main.tsx
    components/
      OrderListInput.tsx      (발주 입력: 엑셀 붙여넣기·수동·이전 발주 복제)
      ComparisonTable.tsx     (개당 실가 오름차순 비교 테이블)
      ReportView.tsx          (누적 절약액·월별 리포트)
      LoginModal.tsx          (쿠팡·네이버 WebView 로그인 안내 모달)
      ProgressBar.tsx         (병렬 조회 진행률)
      StatusBadge.tsx         (플랫폼별 상태: ok/blocked/timeout)
    content-scripts/          (WebView 에 주입되는 파싱 스크립트)
      coupang-parser.ts       (JSON-LD 추출 → {price, shipping, options})
      naver-parser.ts         (__PRELOADED_STATE__ 추출 → 정규화)
      common/
        extractors.ts         (공통 헬퍼: JSON-LD, meta tag, price regex)
    types/
      api.ts                  (백엔드 API 스키마)
      parser.ts               (파서 결과 타입)
    api/
      client.ts               (fetch 래퍼 + JWT)
      endpoints.ts            (엔드포인트 상수)
    hooks/
      useProcurement.ts
      useAuth.ts
    i18n/
      messages/ko.json        (UI 텍스트는 i18n 키로)
  package.json
  tsconfig.json
  vite.config.ts
```

### 4. WebView 매니저 아키텍처
- `webview_manager.rs` 는 플랫폼별(쿠팡/네이버) WebView 풀을 관리한다.
  - 사장 로그인용 "foreground" WebView 는 사용자가 직접 볼 수 있는 창으로 생성(메인 창의 child).
  - 조회용 "background" WebView 는 `visible: false` 로 생성해 백그라운드에서 탐색·파싱 수행.
- 생명주기:
  1. 앱 기동 시 플랫폼당 1개의 foreground WebView 를 lazy 생성(사장이 로그인 필요 시에만 가시화).
  2. 비교 시작 시 품목 수에 따라 background WebView 를 `min(품목수, 3)` 개까지 생성(동시성 상한 3).
  3. 조회 완료 후 background WebView 는 즉시 파괴(`webview.close()`)해 메모리 회수.
  4. 세션 쿠키는 앱 data dir 에 자동 영속화되므로 재실행 시 복구.
- 동시성 상한 3의 근거: Akamai 탐지 완화 + 개인 PC 리소스 보호. 병렬 제한은 `tokio::sync::Semaphore` 로 구현.
- 대안(iframe 내 다중 webview, puppeteer 연동 등)은 세션 격리·자동화 정밀도가 떨어져 제외.

### 5. DOM 파싱 스크립트 주입 전략
- `content-scripts/*.ts` 를 Vite 로 번들해 `src-tauri/assets/` 에 단일 JS 문자열로 내장.
- 주입 시점: WebView 가 해당 URL 의 `DOMContentLoaded` + 추가 지연(300-600ms, SPA 의 XHR 완료 대기) 후.
- 실행 절차:
  1. `webview.eval("window.__PARSER_RESULT__ = null;")` 로 플래그 초기화.
  2. 번들 문자열을 `webview.eval(bundle_js)` 로 주입.
  3. 파서는 파싱 완료 시 `window.__PARSER_RESULT__ = {...}` 를 세팅.
  4. Rust 는 `webview.eval("JSON.stringify(window.__PARSER_RESULT__)")` 를 폴링(최대 10초, 200ms 간격) 하며 결과 회수.
  5. 파싱 결과를 Rust 구조체(`ParsedProduct`) 로 역직렬화.
- 폴링 대신 Tauri 의 `emit` / IPC 를 파서 스크립트에서 호출할 수 있으면 교체(Tauri 2.x 의 webview → host IPC 경로는 공식 docs 재확인 후 선택) [교차검증 필요].
- 쿠팡 파서(`coupang-parser.ts`):
  - 우선순위 1: `<script type="application/ld+json">` JSON-LD 의 `offers.price`, `offers.priceCurrency`.
  - 우선순위 2: `meta[property="product:price:amount"]` 백업.
  - 배송비: 페이지 내 로켓/일반 배송 라벨 selector + shipping policy 룰.
- 네이버 스마트스토어 파서(`naver-parser.ts`):
  - `window.__PRELOADED_STATE__` 에서 `productDetail.A.product.salePrice`, `options`, `shippingInfo` 추출.
  - 옵션별 가격: `options[].salePrice` 배열.

### 6. 쿠키 / 세션 관리
- 세션 쿠키는 WebView data dir 에 자동 영속화:
  - Windows: `%LOCALAPPDATA%\<bundleId>\EBWebView\`.
  - macOS: `~/Library/WebKit/<bundleId>/WebsiteData/`.
- Tauri 2.x 의 `set_cookie` API 미구현(GitHub issue #11691 OPEN) 상태 → MVP 에서는 **사용자가 앱 내 foreground WebView 로 직접 로그인**하는 방식으로 해결.
- 프로그램 측에서 세션 상태를 읽어 "로그인 필요" 여부를 판단해야 할 때는 `webview.eval("document.cookie")` 로 non-HttpOnly 쿠키만 읽어 존재 여부를 유추(HttpOnly 는 보장 못함 → 실패하면 "WebView 에서 로그인 후 다시 시도" UX 로 유도) [교차검증 필요 — POC 필수].
- 사장에게는 "프로그램이 로그인 정보를 서버로 보내지 않고 PC 에만 저장" 을 앱 내 고지문으로 명시.

### 7. Human-like Delay 주입
- WebView 이동·클릭·탭 전환·파서 주입 사이에 `tokio::time::sleep(Duration::from_millis(rand_between(200, 800)))`.
- 품목 간 조회 간격: `rand_between(800, 2000)ms`.
- 한 쿠팡 세션에서 연속 5개 품목 조회 후 30-60초 냉각.
- 공식적으로 "우회" 가 아닌 "비기계적 리듬" 수준으로 유지(사장 본인 조회이므로 법적 성격 동일).
- 근거: Akamai Bot Manager 는 요청 간격의 분산·클릭 패턴·Timing API 를 통합 평가하므로, 균일 간격이 아닌 jitter 만으로도 상당히 완화됨 [교차검증 필요 — Akamai 공식 기술 문서 재확인].

### 8. 백엔드 통신 (JWT 인증)
- 로그인: 카카오 OAuth → 백엔드 `POST /api/v1/auth/kakao` → JWT 수령.
- JWT 보관: 1순위 OS keyring (`keyring` crate), 2순위 `tauri-plugin-sql` SQLite + OS DPAPI/Keychain 암호화.
- 토큰 갱신: access 만료 15분 전에 refresh 토큰으로 갱신(reqwest middleware).
- 구독 확인: 앱 기동 시 + 비교 시작 전 `GET /api/v1/subscription/status` 호출, `status != "active"` 면 업그레이드 모달 표시.
- 발주/결과 제출: `POST /api/v1/procurement/orders` (입력 items) → `POST /api/v1/procurement/results` (파싱·계산 결과).
- 리포트 조회: `GET /api/v1/procurement/reports` 로 누적 절약액 표시.

### 9. 오프라인 저장
- `tauri-plugin-sql` + SQLite 로 로컬 DB 보관.
- 저장 항목: 최근 발주 리스트(복제용), 최근 비교 결과 스냅샷(읽기 전용), JWT, 사장 설정.
- 인터넷 단절 시: 로컬 스냅샷으로 UI 렌더, "오프라인 모드" 배너 표시, 재연결 시 동기화.
- 저장 경로: Tauri 의 `app_data_dir()` 하위. 암호화는 MVP 에서는 OS 레벨 보호만(파일 시스템 권한), post-MVP 에서 SQLCipher 검토.

### 10. 자동 업데이트
- `tauri-plugin-updater` + Ed25519 서명.
- 배포 채널:
  - MVP pilot: GitHub Releases (`latest.json` manifest + `.dmg`/`.msi` 바이너리).
  - 프로덕션: 자체 CDN(CloudFront 또는 Cloudflare R2)로 전환 검토.
- 서명 키 관리: 개인키는 password manager(1Password) 또는 로컬 `~/.tauri/` + 백업. CI 빌드 시 secret 으로 주입.
- 업데이트 체크 주기: 앱 기동 시 1회 + 사용자 수동 "업데이트 확인" 버튼.
- 사용자 경험: 백그라운드 다운로드 → "업데이트 준비 완료" 토스트 → 사용자 승인 시 재시작.

### 11. 코드 사이닝
- macOS:
  - Apple Developer Program $99/year(Developer ID Application + 무제한 notarization).
  - 빌드 파이프라인: `codesign --deep --options runtime --entitlements ...` → `notarytool submit --wait` → `stapler staple` → `.dmg` 생성.
  - CI: GitHub Actions + `APPLE_CERTIFICATE_BASE64`, `APPLE_APP_SPECIFIC_PASSWORD` secrets.
- Windows:
  - OV(Organization Validation) 인증서 $65-200/year. 2026-02-23 CA/B Forum 룰 변경으로 인증서 최대 15개월.
  - 공급자 후보: DigiCert, Sectigo, SSL.com [교차검증 필요 — 2026-04 기준 실가·HSM 요구사항].
  - 빌드: `signtool.exe sign /fd SHA256 /tr <timestamp> ...`.
- [교차검증 필요] 2026 기준 Apple notarization 최신 절차(Apple Silicon + Intel universal binary), Windows EV vs OV 선택 가이드.

### 12. 관측성
- 프론트 로그: 자체 로거(`console.log` 금지) → Rust 의 `commands::log` 로 전달 → `tracing` + 파일 로테이션.
- Rust 로그: `tracing` + `tracing-appender` 로 `app_log_dir()` 에 일별 rotation.
- 크래시 리포트: `sentry-rust` (MVP 후반 도입 검토).
- 사용자 동의 기반 텔레메트리: 기동 시 opt-in 모달. 익명 집계(파싱 성공률, 플랫폼별 평균 응답시간)만 수집.

### 13. 에러 처리 / 리트라이
- 플랫폼별 실패 모드:
  - 로그인 필요(세션 만료): LoginModal 표시 → foreground WebView 안내.
  - Akamai 차단(쿠팡): 3회 재시도(15/30/60초 간격) 후 실패 시 "쿠팡 일시 차단 — 나중에 다시 시도" 배너.
  - 타임아웃: 품목 단위로 독립 처리, 실패 품목만 "재시도" 버튼.
- 백엔드 호출: reqwest + 지수 백오프(`tokio-retry`), 5xx/네트워크 에러만 재시도.
- 모든 에러는 `thiserror` 기반 `AppError` enum 으로 통일, 프론트에는 i18n 키(`errors.*`) 로 전달.

### 14. 보안
- JWT 토큰: OS keyring 우선, 파일 저장 시 최소 권한(0600).
- HTTPS 필수: 백엔드 통신은 `https://` 만 허용, HSTS preload.
- CORS: 백엔드 측에서 앱 origin(`tauri://localhost`) 만 화이트리스트.
- WebView CSP: Tauri 메인 창은 strict CSP, 쿠팡/네이버 WebView 는 해당 사이트 원래 CSP 사용(조작 금지).
- `tauri.conf.json` 의 `allowlist` / `capabilities` 는 최소 권한 원칙(fs 권한은 `app_data_dir` 범위로 제한).

### 15. i18n
- 사장 UI 텍스트는 전부 `src/i18n/messages/*.json` 키로 관리.
- MVP 는 한국어(ko) 만 지원, 구조는 다국어 확장 가능하게 준비.
- 에러 메시지·토스트도 i18n 키로.

## Risks / Trade-offs

- **[Tauri 2.0 `set_cookie` 미구현]** → MVP 에서는 사장이 앱 내 foreground WebView 로 직접 로그인하는 UX 로 우회. `webview.eval("document.cookie=...")` 는 HttpOnly 쿠키에 영향을 못 주므로 POC 로 한계 확인 후 결정 [교차검증 필요].
- **[Akamai 봇 탐지 강화]** → UA·fingerprint 는 시스템 브라우저 수준이지만 클릭/탭 전환 패턴은 탐지 가능. human-like delay + 동시성 3 + 냉각시간으로 완화. 반복 차단 시 사장에게 "쿠팡 측이 일시 차단" 안내.
- **[WebView2 업데이트로 인한 셀렉터 붕괴]** → DOM 파서를 `content-scripts/selectors.ts` 한 곳에 모으고, 파서 실패 시 백엔드로 원본 HTML/state 를 (사용자 동의 하에) 업로드해 패치 대응.
- **[코드 사이닝 비용/절차 장벽]** → Apple $99 + Windows $65-200 예산 확보, 초기 pilot 은 "설치 시 경고 무시" 가이드 문서도 병행 준비.
- **[Rust 러닝커브]** → `commands.rs`/`api_client.rs`/`webview_manager.rs` 핵심 3개 모듈만 Rust, 나머지 로직은 TypeScript 로 몰아 학습 부담 축소.
- **[사장 PC 리소스 부담]** → 동시성 상한 3 + background WebView 즉시 파괴 + 메모리 모니터링(Task Manager/Activity Monitor 수준).
- **[업데이트 서버 가용성]** → 초기엔 GitHub Releases 로 단순화. 유료 사장 수 증가 시 CDN 전환.
- **[법적 해석 변동]** → 사장 본인 계정·본인 PC 전제가 무너지면(예: 서버 배포 요구) 전면 재평가. README 와 앱 내 안내에 명시.
- **[Windows EV 인증서 vs OV]** → MVP 는 OV 로 시작(비용 절감), SmartScreen 평판 누적 후 필요 시 EV 로 전환. HSM 필수 여부는 공급자별 상이 [교차검증 필요].

## Migration Plan

신규 앱이라 마이그레이션은 없다. 초기 pilot 배포 절차:

1. `tauri-app/` 스캐폴드 → `pnpm create tauri-app` 또는 수동 구성.
2. `.env.local` 에 `VITE_BACKEND_URL`, `VITE_KAKAO_CLIENT_ID` 설정.
3. 개발: `pnpm tauri dev`.
4. 빌드: `pnpm tauri build` → `src-tauri/target/release/bundle/` 하위에 `.dmg`/`.msi` 생성.
5. 코드 사이닝 + notarization(macOS) / signtool(Windows) → `.dmg`/`.msi` 재생성.
6. GitHub Release 에 바이너리 + `latest.json` 업로드.
7. 사장에게 링크 전달 또는 USB 로 .dmg/.msi 직접 전달.

롤백: 사장 PC 에서 앱 삭제 → 이전 버전 설치(자동 업데이트 롤백은 MVP 에서는 수동 절차).

기존 Streamlit UI(`backend/ui/streamlit_app.py`)는 삭제하지 않고 내부 QA 용도로 유지하되, 사용자 대면 UI 로는 사용하지 않는다.

## Open Questions

- Tauri 2.x multi-webview 의 정확한 API 시그니처(`WebviewWindow::add_child()` vs `WebviewBuilder::new()`) 와 다중 webview 에서 CSP/쿠키 격리의 공식 문서 확인 — `[교차검증 필요]`
- `set_cookie` 대체로 `webview.eval("document.cookie=...")` 가 쿠팡·네이버에서 실제로 인증에 사용되는 세션 쿠키를 설정할 수 있는지 POC — `[교차검증 필요]`
- Apple notarization 최신 절차(Xcode 16, notarytool 최신) 와 Universal binary 요구 여부 — `[교차검증 필요]`
- Windows OV 인증서 실가(2026-04 기준) 및 공급자별 HSM 의무 여부 — `[교차검증 필요]`
- 카카오 OAuth 데스크톱 앱 방식 구현(로컬 루프백 redirect vs deep link `myapp://`) — POC 시 결정
- 자동 담기 기능의 법적 해석 — pilot 피드백 후 법무 자문 또는 사용자 수동 확인으로 안전하게 유지
