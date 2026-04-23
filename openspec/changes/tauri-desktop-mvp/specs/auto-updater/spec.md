## ADDED Requirements

### Requirement: tauri-plugin-updater 통합

시스템은 `tauri-plugin-updater` 를 `tauri.conf.json` 의 `bundle` + `plugins.updater` 섹션에 통합해야 한다(MUST). 업데이트 manifest 는 `latest.json` 형식이며, 바이너리는 Ed25519 서명을 포함해야 한다.

#### Scenario: 플러그인 등록
- **WHEN** 앱이 시작된다
- **THEN** Rust 메인(`main.rs`) 은 `.plugin(tauri_plugin_updater::Builder::new().build())` 로 플러그인을 등록한다

#### Scenario: manifest URL 구성
- **WHEN** `tauri.conf.json` 이 로드된다
- **THEN** `plugins.updater.endpoints` 에 `https://github.com/<owner>/<repo>/releases/latest/download/latest.json` (또는 자체 CDN URL) 이 설정되어 있고, `plugins.updater.pubkey` 에 Ed25519 공개키가 기록되어 있다

### Requirement: Ed25519 서명 기반 검증

모든 업데이트 바이너리는 Ed25519 개인키로 서명되어야 하며, 앱은 번들된 공개키로 서명을 검증한 후에만 업데이트를 적용해야 한다(MUST). 서명 생성은 `tauri signer generate` 및 `tauri signer sign` CLI 로 수행한다.

#### Scenario: 서명 검증 성공
- **WHEN** `latest.json` 이 가리키는 바이너리의 Ed25519 서명이 번들된 공개키와 일치한다
- **THEN** 업데이터는 바이너리를 다운로드·검증·적용하고 재시작을 요청한다

#### Scenario: 서명 검증 실패
- **WHEN** 바이너리의 서명이 일치하지 않는다
- **THEN** 업데이터는 업데이트를 거부하고 `updater.signature_mismatch` 에러를 로그에 기록하며, 사용자에게 "업데이트 검증 실패" 알림을 표시한다

### Requirement: 업데이트 체크 주기

앱은 다음 시점에 업데이트를 확인해야 한다(SHALL):
1. 앱 기동 후 5초 이내(네트워크 연결 상태 확인 후).
2. 사용자가 "업데이트 확인" 메뉴 항목을 클릭할 때.
3. 앱이 24시간 이상 연속 실행 중일 때 백그라운드 재확인.

업데이트 체크 호출은 병렬로 여러 번 발행되지 않도록 mutex 로 보호한다.

#### Scenario: 기동 시 자동 체크
- **WHEN** 앱이 시작되고 5초가 경과한다
- **THEN** 앱은 `check()` 를 1회 호출하고, 업데이트가 있으면 프론트에 이벤트를 emit 해 "업데이트 사용 가능" 배너를 표시한다

#### Scenario: 중복 체크 방지
- **WHEN** 기동 자동 체크와 사용자 수동 체크가 거의 동시에 발생한다
- **THEN** 시스템은 mutex 로 한 번에 하나의 체크만 실행되도록 보장한다

### Requirement: 사용자 승인 기반 적용

업데이트는 자동으로 즉시 적용되지 않고, 사용자에게 승인을 요구해야 한다(MUST):
1. 다운로드는 백그라운드에서 자동 수행.
2. 다운로드 완료 시 "업데이트 준비 완료" 토스트 + "지금 재시작" / "나중에" 버튼 표시.
3. 사용자가 "지금 재시작" 을 클릭하면 앱이 재시작되며 새 버전으로 전환.

#### Scenario: 승인 후 재시작
- **WHEN** 사용자가 "지금 재시작" 을 클릭한다
- **THEN** 앱은 현재 상태(진행 중 비교 작업) 를 SQLite 에 저장하고 새 버전으로 재시작한다

#### Scenario: 나중에 선택
- **WHEN** 사용자가 "나중에" 를 클릭한다
- **THEN** 앱은 현재 세션을 유지하고, 다음 기동 시 다시 업데이트 배너를 표시한다

### Requirement: 배포 채널 및 CI

업데이트 바이너리는 다음 채널로 배포되어야 한다(SHALL):
- **MVP pilot**: GitHub Releases (`latest.json` manifest + `.dmg`(macOS universal) + `.msi`(Windows x64)).
- **프로덕션**: 자체 CDN(CloudFront 또는 Cloudflare R2) 로 전환 가능하도록 endpoint 환경변수로 구성.

CI(GitHub Actions) 는 매 릴리즈마다 다음을 수행한다:
1. macOS runner 에서 universal binary 빌드 + codesign + notarize.
2. Windows runner 에서 x64 빌드 + signtool 서명.
3. 각 바이너리에 `tauri signer sign` 으로 Ed25519 서명 부착.
4. `latest.json` 에 버전·다운로드 URL·signature 기록.
5. GitHub Release 에 업로드.

#### Scenario: 릴리즈 파이프라인
- **WHEN** `v0.2.0` 태그가 푸시된다
- **THEN** GitHub Actions 가 macOS + Windows 바이너리를 자동 빌드·서명·업로드하고 `latest.json` 을 갱신한다

#### Scenario: 롤백
- **WHEN** `v0.2.0` 에서 심각한 버그가 발견되었다
- **THEN** 운영자는 `latest.json` 을 수동으로 `v0.1.9` 를 가리키도록 되돌려 자동 업데이트가 이전 버전으로 롤백되게 한다(MVP 수동 절차, post-MVP 자동화 검토)

### Requirement: 개인키 관리

Ed25519 개인키는 안전하게 보관되어야 한다(MUST):
- 개발자 로컬: `~/.tauri/` 하위 + 비밀번호 보호 + 1Password/LastPass 백업.
- CI: GitHub Actions secret(`TAURI_SIGNING_PRIVATE_KEY`, `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`)으로 주입.
- 키 유출 시 절차: 새 키 생성 → 앱 번들 교체 → 사용자에게 전버전 수동 재설치 공지(자동 업데이트 불가).

#### Scenario: CI 서명
- **WHEN** GitHub Actions 가 릴리즈 빌드를 수행한다
- **THEN** 시크릿에서 개인키를 읽어 `tauri signer sign` 을 실행하고, 시크릿은 로그에 노출되지 않는다

#### Scenario: 키 유출 대응
- **WHEN** 개인키가 유출되었음이 확인된다
- **THEN** 운영자는 새 키 쌍을 생성하고, 다음 릴리즈에 새 공개키를 번들한 뒤, 사용자에게 "일시적으로 수동 재설치 필요" 공지를 전달한다

### Requirement: 업데이트 실패 회복

업데이트 다운로드·서명 검증·설치 단계에서 실패가 발생하면 시스템은 다음과 같이 회복해야 한다(SHALL):
- 다운로드 실패: 3회 재시도(10/30/60초 간격) 후 포기.
- 서명 검증 실패: 재시도하지 않고 즉시 실패 로그 기록.
- 설치 실패: 이전 바이너리 유지, 다음 기동 시 재시도.

실패 정보는 로컬 로그에 기록되고, opt-in 텔레메트리가 켜져 있으면 익명 카운트만 백엔드로 전송한다.

#### Scenario: 다운로드 재시도
- **WHEN** 업데이트 다운로드가 네트워크 오류로 실패한다
- **THEN** 업데이터는 10초 후 재시도, 실패 시 30초 후, 그 다음 60초 후 재시도하고, 모두 실패하면 배너에 "업데이트 다운로드 실패 — 다음 기동에 재시도" 를 표시한다

#### Scenario: 설치 실패 복구
- **WHEN** 업데이트 설치 중 파일 쓰기 권한 오류가 발생한다
- **THEN** 앱은 이전 바이너리로 계속 동작하고 다음 기동 시 다시 시도한다
