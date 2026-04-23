## ADDED Requirements

### Requirement: 발주 리스트 입력

시스템은 사장이 발주 품목을 입력하는 세 가지 방식을 지원해야 한다(SHALL):
1. **엑셀 붙여넣기** — textarea 에 탭/줄바꿈 구분 텍스트를 붙여넣으면 품목명·수량 열로 자동 파싱.
2. **수동 입력** — "행 추가" 버튼으로 품목명·예상 수량을 한 줄씩 입력.
3. **이전 발주 복제** — SQLite 에 저장된 최근 30일 발주 리스트에서 드롭다운으로 선택.

입력은 최소 1개, 최대 50개 품목까지 허용하며, 품목명 빈 문자열은 행 단위로 제외한다.

#### Scenario: 엑셀 붙여넣기
- **WHEN** 사장이 textarea 에 `콜라 500ml\t12\n과자\t5` 를 붙여넣는다
- **THEN** 시스템은 `[{name: "콜라 500ml", qty: 12}, {name: "과자", qty: 5}]` 로 파싱해 테이블에 표시한다

#### Scenario: 이전 발주 복제
- **WHEN** 사장이 "지난주 월요일 발주" 를 선택한다
- **THEN** 시스템은 SQLite 에서 해당 orders 레코드를 로드해 입력 테이블에 프리필한다

#### Scenario: 50개 초과 입력
- **WHEN** 사장이 51개 품목을 입력한다
- **THEN** 시스템은 "한 번에 최대 50개까지 비교할 수 있습니다" i18n 메시지를 표시하고 51번째 행부터 잘라낸다

### Requirement: 비교 실행 오케스트레이션

사장이 "비교 시작" 을 클릭하면 시스템은 다음 순서로 처리해야 한다(MUST):
1. 구독 상태 확인: `GET /api/v1/subscription/status` 호출, 비활성이면 업그레이드 모달 표시 후 중단.
2. 발주 제출: `POST /api/v1/procurement/orders` 로 발주 ID 수령.
3. 품목별 병렬 조회: WebView 매니저가 동시 3개 제한으로 쿠팡·네이버 상세 페이지 로드·파싱.
4. 개당 실가 계산: Rust `unit_price`·`shipping_policy`·`ranking` 서비스 통과.
5. 결과 업로드: `POST /api/v1/procurement/results` 로 파싱·계산 결과 전송.
6. UI 렌더: `ComparisonTable` 에 개당 실가 오름차순 표시.

각 품목은 독립적으로 처리되며, 한 품목 실패가 전체를 차단하지 않는다.

#### Scenario: 정상 플로우
- **WHEN** 사장이 10개 품목에 대해 비교 시작을 클릭한다
- **THEN** 시스템은 구독 확인 → 발주 제출 → 품목별 병렬 조회(동시 3개) → 결과 업로드 순으로 진행하고 UI 에 정렬된 비교 테이블을 표시한다

#### Scenario: 구독 미활성
- **WHEN** `GET /api/v1/subscription/status` 가 `status: "inactive"` 를 반환한다
- **THEN** 시스템은 비교 실행을 중단하고 업그레이드 모달을 표시한다

#### Scenario: 한 품목 실패
- **WHEN** 10개 품목 중 품목 3 이 `akamai_blocked` 로 실패한다
- **THEN** 시스템은 나머지 9개 품목의 결과를 정상 표시하고, 품목 3 은 "재시도" 버튼과 함께 에러 상태로 표시한다

### Requirement: 개당 실가 계산

시스템은 각 품목의 각 옵션에 대해 `unit_price = (option_price + shipping_fee) / unit_quantity` 로 개당 실가를 계산해야 한다(MUST). 기준단위는 Google Merchant 스키마(`g`, `ml`, `ct`, `sheet`) 를 준용하고 표시는 `100g`·`100ml`·`1ct` 단위로 환산한다.

배송비는 다음 정책을 따른다(SHALL):
- 쿠팡 로켓 비회원: 실결제액 19,800원 이상일 때 0, 미만일 때 3,000원.
- 스마트스토어: 셀러의 `free_threshold` 이상일 때 0, 미만일 때 상세 페이지에 명시된 배송비.
- 와우 멤버십: MVP 범위 외(사용자 수동 확인).

수량 파싱이 실패하면 `unit_price: null`, `unit_price_confidence: "low"` 를 반환한다(0 나눗셈 방지).

#### Scenario: 쿠팡 로켓 임계치 초과
- **WHEN** 쿠팡 로켓 옵션 `option_price = 25000`, 수량 12개다
- **THEN** 시스템은 `shipping_fee = 0` 을 적용해 `unit_price = 2083.33` (원/개)를 계산한다

#### Scenario: 수량 파싱 실패
- **WHEN** 옵션 텍스트가 "스페셜 패키지"처럼 수량 힌트가 없다
- **THEN** 시스템은 `unit_quantity: null`, `unit_price: null`, `unit_price_confidence: "low"` 를 반환하고 해당 옵션은 정렬 끝으로 밀어낸다

### Requirement: 결과 정렬 및 표시

비교 테이블은 다음 순서로 정렬되어야 한다(MUST):
1. 1순위: 품목별 그룹화(입력 순서 유지).
2. 2순위: 그룹 내 `unit_price` 오름차순.
3. 3순위: `unit_price` 가 `null` 인 옵션은 그룹 끝.

각 행에는 품목명·플랫폼 배지·옵션 텍스트·옵션가·배송비·실수량·개당 실가·상품 URL 링크·신뢰도 배지(`high`/`medium`/`low`)를 표시한다.

#### Scenario: 품목별 그룹화
- **WHEN** 사장이 `[콜라, 과자, 물]` 순서로 입력하고 각 품목마다 여러 옵션이 파싱된다
- **THEN** 비교 테이블은 `[콜라의 옵션들 → 과자의 옵션들 → 물의 옵션들]` 순서로 그룹화되고, 각 그룹 내부는 unit_price 오름차순이다

#### Scenario: 신뢰도 배지
- **WHEN** 한 옵션의 `unit_price_confidence: "low"` 이다
- **THEN** 해당 행에 "추정" 배지가 표시되고, 툴팁으로 "수량 파싱 실패, 참고용" 이 나타난다

### Requirement: 백엔드 리포트 제출 및 조회

시스템은 비교 실행마다 파싱·계산 결과를 백엔드에 업로드해야 한다(SHALL):
- 엔드포인트: `POST /api/v1/procurement/results`
- Payload: 발주 ID, 품목별 옵션 리스트, 각 옵션의 `{platform, price, shipping_fee, unit_quantity, unit_price, parser_version, confidence}`.

사장이 "리포트 보기" 를 클릭하면 `GET /api/v1/procurement/reports` 로 누적 절약액·월별 그래프를 조회한다.

#### Scenario: 결과 업로드
- **WHEN** 비교가 완료되었다
- **THEN** 앱은 10초 이내에 `POST /api/v1/procurement/results` 를 호출해 결과를 업로드하고, 실패 시 SQLite `outbox` 테이블에 보관해 다음 기동 시 재시도한다

#### Scenario: 리포트 조회
- **WHEN** 사장이 리포트 탭을 연다
- **THEN** 앱은 `GET /api/v1/procurement/reports` 를 호출해 `{total_saved, monthly_series, top_platforms}` 를 렌더한다

### Requirement: 오프라인 모드

인터넷이 단절된 경우 시스템은 다음 기능을 오프라인으로 제공해야 한다(SHALL):
- SQLite 에 저장된 최근 30일 발주 리스트 조회(복제용).
- SQLite 에 저장된 최근 10회 비교 결과 스냅샷 조회(읽기 전용).
- 새 비교 실행은 차단하고 "인터넷 연결 후 다시 시도" 배너 표시.

재연결 시 백엔드 동기화 큐(`outbox` 테이블)에 쌓인 제출 내역을 자동 송신한다.

#### Scenario: 오프라인 조회
- **WHEN** 인터넷 단절 상태에서 사장이 앱을 실행한다
- **THEN** 시스템은 "오프라인 모드" 배너를 표시하고, 이전 발주·비교 결과를 SQLite 에서 읽어 렌더한다

#### Scenario: 재연결 동기화
- **WHEN** 인터넷이 복구된다
- **THEN** 앱은 10초 이내에 `outbox` 큐를 flush 해 밀린 결과 업로드를 순차 전송한다
