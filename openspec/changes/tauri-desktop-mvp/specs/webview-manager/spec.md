## ADDED Requirements

### Requirement: 다중 WebView 생성 및 격리

시스템은 Tauri 2.0 의 `WebviewWindow::add_child()` API 를 사용해 메인 창 안에 플랫폼별(쿠팡·네이버) WebView 를 동적으로 생성할 수 있어야 한다(MUST). 각 WebView 는 시스템 기본 브라우저와 격리된 자체 데이터 디렉토리(Windows=WebView2 user data folder, macOS=`~/Library/WebKit/<bundleId>`)를 사용해 쿠키·로컬스토리지·IndexedDB 를 영속화해야 한다.

#### Scenario: foreground 로그인 WebView 생성
- **WHEN** 사용자가 "쿠팡 로그인" 버튼을 클릭한다
- **THEN** 시스템은 쿠팡 전용 foreground WebView 를 `visible: true` 상태로 생성해 `https://login.coupang.com/` 을 표시하고, 사용자가 로그인하면 세션 쿠키가 해당 WebView 의 data dir 에 영속화된다

#### Scenario: background 조회 WebView 생성
- **WHEN** 비교 시작 시 품목별 조회가 필요하다
- **THEN** 시스템은 각 품목마다 `visible: false` 의 background WebView 를 생성해 상세 페이지를 로드하고, 파싱 완료 후 즉시 `webview.close()` 로 파괴해 메모리를 회수한다

#### Scenario: 세션 격리 확인
- **WHEN** 사용자가 시스템 Chrome 에서 쿠팡에 로그인되어 있는 상태에서 앱을 실행한다
- **THEN** 앱 내 WebView 는 시스템 Chrome 의 세션을 공유하지 않으며, 앱 내에서 별도 로그인이 필요하다

### Requirement: 동시성 상한

시스템은 동시에 실행되는 background WebView 수를 **최대 3개**로 제한해야 한다(MUST). 상한은 `tokio::sync::Semaphore` 로 구현하며, 추가 요청은 슬롯이 확보될 때까지 대기한다.

#### Scenario: 품목 수가 상한을 초과한다
- **WHEN** 20개 품목에 대해 비교 요청이 들어온다
- **THEN** 시스템은 동시에 최대 3개 WebView 만 활성화하고, 슬롯이 비면 다음 품목을 순차로 투입한다

#### Scenario: 조회 완료 후 슬롯 반환
- **WHEN** 한 품목의 파싱이 완료되어 WebView 가 파괴된다
- **THEN** 시스템은 해당 슬롯을 즉시 다음 대기 품목에 할당한다

### Requirement: 세션 영속화 및 복구

WebView 의 쿠키·로컬스토리지는 앱의 data dir 에 자동 영속화되어 앱 재시작 후에도 복구되어야 한다(MUST). 단, `set_cookie` API 미구현(GitHub issue #11691) 때문에 프로그램 측에서 쿠키를 직접 주입할 수는 없으며, 세션 획득은 **사용자가 앱 내 foreground WebView 로 직접 로그인**하는 방식으로만 이뤄진다.

#### Scenario: 앱 재시작 후 세션 복구
- **WHEN** 사용자가 전날 앱에서 쿠팡에 로그인하고 오늘 앱을 다시 실행한다
- **THEN** 앱 내 쿠팡 WebView 는 로그인 상태로 복구되며 재로그인이 필요 없다 (쿠팡 측 세션 TTL 내)

#### Scenario: 세션 만료 감지
- **WHEN** background WebView 로 쿠팡 상세 페이지를 로드했을 때 로그인 페이지로 리다이렉트된다
- **THEN** 시스템은 해당 품목에 대해 `error.code = "login_required"` 를 반환하고 프론트는 LoginModal 을 표시한다

### Requirement: Human-like Delay

WebView 탐색·파싱 스크립트 주입·탭 전환 사이에 랜덤 지연을 주입해야 한다(SHALL). 구체 범위는 다음과 같다:
- 파싱 스크립트 주입 전 DOM 안정화 대기: 300-600ms
- 품목 간 조회 간격: 800-2000ms
- 동일 쿠팡 세션 5개 품목 조회 후 30-60초 냉각 sleep

#### Scenario: 품목 간 지연 적용
- **WHEN** 품목 A 의 파싱이 완료되어 품목 B 조회를 시작하려 한다
- **THEN** 시스템은 800-2000ms 범위의 랜덤 sleep 후 품목 B 의 WebView 를 생성한다

#### Scenario: 5개 품목 냉각 적용
- **WHEN** 연속 5개 쿠팡 품목이 조회 완료되었다
- **THEN** 시스템은 다음 쿠팡 조회 전에 30-60초 범위의 랜덤 sleep 을 수행한다

### Requirement: WebView 에러 모드

시스템은 WebView 조회 중 발생하는 대표 실패 모드를 구분해 프론트에 전달해야 한다(MUST):
- `login_required` — 로그인 페이지로 리다이렉트됨
- `akamai_blocked` — HTTP 403 또는 "Pardon Our Interruption" 검출
- `timeout` — 품목당 조회 타임아웃 30초 초과
- `parser_failed` — 파싱 스크립트가 결과를 세팅하지 않음

각 에러는 `AppError` enum 의 variant 로 정의하고 프론트에 i18n 키와 함께 전달한다.

#### Scenario: Akamai 차단 검출
- **WHEN** 쿠팡 상세 페이지가 HTTP 403 또는 `document.title` 에 "Pardon Our Interruption" 을 포함한다
- **THEN** 시스템은 해당 품목을 `akamai_blocked` 로 마킹하고, 3회 재시도(15/30/60초 간격) 후에도 실패하면 최종 실패 상태로 고정한다

#### Scenario: 조회 타임아웃
- **WHEN** 한 품목의 WebView 로드가 30초를 초과한다
- **THEN** 시스템은 WebView 를 파괴하고 해당 품목을 `timeout` 으로 마킹한다

#### Scenario: 파싱 결과 없음
- **WHEN** 10초 폴링 동안 `window.__PARSER_RESULT__` 가 `null` 이거나 정의되지 않는다
- **THEN** 시스템은 `parser_failed` 를 반환하고 프론트는 "해당 페이지 구조 변경 감지" 배너를 표시한다
