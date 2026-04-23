## 1. 프로젝트 초기화

- [ ] 1.1 `tauri-app/` 디렉토리 생성 및 `pnpm create tauri-app` 또는 수동 스캐폴드 (React + TypeScript + Vite)
- [ ] 1.2 `tauri-app/package.json` 구성 (react@18, react-dom@18, typescript@5, @tauri-apps/api@2, @tauri-apps/plugin-updater, @tauri-apps/plugin-sql, vite, zod)
- [ ] 1.3 `tauri-app/tsconfig.json` (strict mode)
- [ ] 1.4 `tauri-app/vite.config.ts` + `tauri-app/src-tauri/Cargo.toml` (tauri@2, tauri-plugin-updater@2, tauri-plugin-sql@2, tauri-plugin-http@2, reqwest, serde, serde_json, tokio, rand, tracing, thiserror)
- [ ] 1.5 `tauri-app/src-tauri/tauri.conf.json` 기본 설정 (앱 이름, bundleId, icons, updater endpoint placeholder)
- [ ] 1.6 `tauri-app/src-tauri/capabilities/default.json` 최소 권한 capability 정의
- [ ] 1.7 `.env.example` (VITE_BACKEND_URL, VITE_KAKAO_CLIENT_ID, TAURI_SIGNING_PRIVATE_KEY, TAURI_SIGNING_PRIVATE_KEY_PASSWORD)
- [ ] 1.8 `.gitignore` (`src-tauri/target/`, `dist/`, `node_modules/`, `*.dmg`, `*.msi`, `*.env.local`)
- [ ] 1.9 `tauri-app/README.md` 초안 (개발·빌드·서명 절차)

## 2. 메인 창 UI 스켈레톤

- [ ] 2.1 `src/main.tsx` + `src/App.tsx` 라우팅 구조 (홈, 비교결과, 리포트, 설정)
- [ ] 2.2 `src/components/OrderListInput.tsx` — 발주 입력(엑셀 붙여넣기 textarea, 수동 입력 행 추가, 이전 발주 복제 드롭다운)
- [ ] 2.3 `src/components/ComparisonTable.tsx` — 개당 실가 오름차순 비교 테이블(품목명·플랫폼·옵션·가격·배송비·실수량·개당 실가·링크)
- [ ] 2.4 `src/components/ReportView.tsx` — 누적 절약액·월별 그래프(간단 chart)
- [ ] 2.5 `src/components/LoginModal.tsx` — 쿠팡/네이버 로그인 안내 모달 + foreground WebView 오픈 버튼
- [ ] 2.6 `src/components/ProgressBar.tsx` — 조회 진행률 + 플랫폼별 상태 배지
- [ ] 2.7 `src/components/StatusBadge.tsx` — 상태 표시(ok/blocked/timeout/login-required)
- [ ] 2.8 `src/i18n/messages/ko.json` — 모든 UI 텍스트 i18n 키 매핑
- [ ] 2.9 `src/hooks/useAuth.ts`, `src/hooks/useProcurement.ts` — Context + useReducer 기반 상태 관리

## 3. WebView 매니저 (Rust)

- [ ] 3.1 `src-tauri/src/main.rs` — Tauri 엔트리, 플러그인 등록(updater, sql, http), 메인 창 생성
- [ ] 3.2 `src-tauri/src/webview_manager.rs` — WebView 풀 구조체, foreground/background 분리, `add_child()` 호출
- [ ] 3.3 동시성 상한 3 구현 — `tokio::sync::Semaphore` 기반
- [ ] 3.4 WebView 라이프사이클 — 생성/파괴/재사용 로직, 사용 후 `webview.close()` 로 메모리 회수
- [ ] 3.5 `src-tauri/src/error.rs` — `AppError` enum (thiserror) + 프론트 전달용 i18n 키 맵핑
- [ ] 3.6 `src-tauri/src/commands.rs` — `#[tauri::command]` 진입점 (open_login_webview, run_comparison, cancel_comparison 등)

## 4. DOM 파싱 스크립트

- [ ] 4.1 `src/content-scripts/common/extractors.ts` — JSON-LD 추출, meta tag 추출, price regex 공통 헬퍼
- [ ] 4.2 `src/content-scripts/coupang-parser.ts` — JSON-LD 우선, meta tag 백업, 배송비·로켓 라벨 감지
- [ ] 4.3 `src/content-scripts/naver-parser.ts` — `__PRELOADED_STATE__` 역직렬화, 옵션 배열·shippingInfo 추출
- [ ] 4.4 Vite 빌드 구성 — content-scripts 를 단일 JS 문자열로 번들해 `src-tauri/assets/` 에 내장
- [ ] 4.5 `src-tauri/src/parser_bridge.rs` — 번들 주입, `window.__PARSER_RESULT__` 폴링, JSON 역직렬화(serde)
- [ ] 4.6 주입 실패/타임아웃 핸들링 — 10초 폴링 타임아웃, 부분 결과 복구

## 5. 개당 실가 계산 및 집계 (Rust)

- [ ] 5.1 `src-tauri/src/services/unit_price.rs` — `(option_price + shipping_fee) / unit_quantity` 계산, 기준단위 환산(100g/100ml/1ct), null 처리
- [ ] 5.2 `src-tauri/src/services/shipping_policy.rs` — 쿠팡 19,800원 임계치, 스마트스토어 free_threshold, "estimated" confidence 태깅
- [ ] 5.3 `src-tauri/src/services/ranking.rs` — unit_price 오름차순 정렬, null 뒤로, comparable_group 분류
- [ ] 5.4 `src-tauri/src/services/quantity_parser.rs` — 옵션 텍스트 정규식 파서(영역 A 와 동일 7패턴 또는 Rust 버전 포팅)

## 6. 백엔드 API 클라이언트 (Rust)

- [ ] 6.1 `src-tauri/src/api_client.rs` — reqwest 기반 HTTP 클라이언트, JWT Bearer 주입, 지수 백오프(tokio-retry)
- [ ] 6.2 JWT 저장/갱신 — `src-tauri/src/auth.rs` + keyring crate 우선, fallback 으로 tauri-plugin-sql
- [ ] 6.3 `POST /api/v1/auth/kakao` 호출 — 카카오 OAuth 콜백 처리(로컬 루프백 server 또는 deep link)
- [ ] 6.4 `GET /api/v1/shops/me` — 가게 정보 조회 + 프론트 컨텍스트 주입
- [ ] 6.5 `POST /api/v1/procurement/orders` — 발주 제출 (items JSONB)
- [ ] 6.6 `POST /api/v1/procurement/results` — 파싱·계산 결과 업로드
- [ ] 6.7 `GET /api/v1/procurement/reports` — 누적 절약액 리포트 조회
- [ ] 6.8 `GET /api/v1/subscription/status` — 구독 상태 확인 (기동 시 + 비교 시작 전)
- [ ] 6.9 `src/api/client.ts` + `src/api/endpoints.ts` — 프론트 측에서도 일부 직접 호출(리포트 렌더 등) 시 zod 스키마 검증

## 7. 로그인 UX (쿠팡 / 네이버)

- [ ] 7.1 LoginModal + Rust command `open_login_webview(platform)` — foreground WebView 띄우기
- [ ] 7.2 로그인 완료 감지 — URL 변화 또는 주요 쿠키 존재 감지(non-HttpOnly 한정)
- [ ] 7.3 "로그인 정보는 PC 에만 저장되고 서버로 전송되지 않습니다" 고지문을 모달에 표시
- [ ] 7.4 세션 만료 시 자동 재로그인 유도 UX

## 8. Human-like Delay & 에러 핸들링

- [ ] 8.1 `src-tauri/src/services/pacing.rs` — 품목 간 800-2000ms, 탐색 단계 간 200-800ms 랜덤 sleep
- [ ] 8.2 동일 쿠팡 세션 5개 품목 후 30-60초 냉각 로직
- [ ] 8.3 Akamai 차단 감지(HTTP 403 + "Pardon Our Interruption" 또는 JS challenge URL) → 3회 재시도(15/30/60s)
- [ ] 8.4 품목별 독립 실패 처리 — 한 품목 실패가 전체를 막지 않도록 Promise.allSettled 패턴
- [ ] 8.5 타임아웃(품목당 30초) + 사용자가 개별 재시도 버튼 제공
- [ ] 8.6 에러 → i18n 키 매핑 (`errors.akamai_blocked`, `errors.login_required`, `errors.timeout` 등)

## 9. 오프라인 저장 (SQLite)

- [ ] 9.1 `tauri-plugin-sql` 설정 + 마이그레이션 파일(`migrations/001_init.sql`)
- [ ] 9.2 테이블: `orders`(발주 스냅샷), `results`(비교 결과 스냅샷), `settings`(사장 설정), `auth_tokens`(암호화된 JWT)
- [ ] 9.3 `src-tauri/src/storage.rs` — CRUD 헬퍼
- [ ] 9.4 인터넷 단절 감지 + "오프라인 모드" 배너 + 재연결 시 자동 동기화 큐

## 10. 자동 업데이트

- [ ] 10.1 `tauri-plugin-updater` 등록 + `tauri.conf.json` 의 `updater` 섹션(endpoint, pubkey) 구성
- [ ] 10.2 Ed25519 키 쌍 생성(`tauri signer generate`) + 개인키 백업 절차 문서화
- [ ] 10.3 `latest.json` manifest 생성 스크립트 (`scripts/publish_update.sh`)
- [ ] 10.4 앱 기동 시 업데이트 체크 + "업데이트 확인" 수동 버튼
- [ ] 10.5 업데이트 다운로드 → "재시작" 토스트 UX
- [ ] 10.6 GitHub Releases 를 초기 배포 채널로 설정

## 11. macOS 코드 사이닝 + Notarization

- [ ] 11.1 Apple Developer Program 가입 + Developer ID Application 인증서 발급
- [ ] 11.2 `tauri.conf.json` 의 `bundle.macOS.signingIdentity`, `bundle.macOS.entitlements` 구성
- [ ] 11.3 `scripts/sign_macos.sh` — codesign + notarytool submit + stapler staple
- [ ] 11.4 Universal binary(aarch64 + x86_64) 빌드 매트릭스
- [ ] 11.5 GitHub Actions `macos-latest` 에서 APPLE_CERTIFICATE_BASE64·APPLE_APP_SPECIFIC_PASSWORD 시크릿으로 CI 자동 서명

## 12. Windows 코드 사이닝

- [ ] 12.1 OV 인증서 공급자 선정(DigiCert / Sectigo / SSL.com) + 구매 [교차검증 필요 — 2026-04 기준 HSM 의무 여부]
- [ ] 12.2 `scripts/sign_windows.ps1` — signtool.exe sign /fd SHA256 /tr <timestamp> /td SHA256
- [ ] 12.3 GitHub Actions `windows-latest` 에서 HSM 연동 또는 PFX 시크릿 기반 서명
- [ ] 12.4 SmartScreen 평판 누적 전략 문서화

## 13. E2E 테스트

- [ ] 13.1 단위 테스트 — Rust 서비스(`unit_price`, `shipping_policy`, `quantity_parser`) `cargo test`
- [ ] 13.2 단위 테스트 — TypeScript 파서(`coupang-parser`, `naver-parser`) Vitest + 고정 HTML 픽스처
- [ ] 13.3 컴포넌트 테스트 — React Testing Library (OrderListInput, ComparisonTable, LoginModal)
- [ ] 13.4 E2E — WebDriver/Tauri e2e 프레임워크로 실제 로그인된 WebView 기반 시나리오(수동 로그인 후 자동 진행)
- [ ] 13.5 테스트 데이터셋 — 쿠팡/네이버 실제 페이지 HTML 30개 이상을 캡처해 픽스처로 보관(민감정보 없이)
- [ ] 13.6 CI — GitHub Actions 로 cargo test + vitest + tsc --noEmit 자동 실행

## 14. 초기 Pilot 배포 가이드 문서

- [ ] 14.1 `tauri-app/docs/INSTALL.md` — 사장용 설치 가이드(macOS: Gatekeeper 우회 경고, Windows: SmartScreen 경고 대응)
- [ ] 14.2 `tauri-app/docs/PRIVACY.md` — 로그인 세션이 PC 에만 저장됨·백엔드로 전송되지 않음 고지
- [ ] 14.3 `tauri-app/docs/TROUBLESHOOTING.md` — 쿠팡 차단·로그인 만료·업데이트 실패 대응
- [ ] 14.4 README.md 갱신 — 프로젝트 루트에 `tauri-app/` 추가 안내
- [ ] 14.5 Pilot 사장 5명 선정 + 피드백 수집 폼(Google Forms 또는 Notion)
- [ ] 14.6 IMPLEMENTATION_PLAN.md 의 "교차검증 필요" 체크리스트를 착수 전 모두 해소
