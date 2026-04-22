## ADDED Requirements

### Requirement: 정규식 기반 7패턴 파서

시스템은 자유 텍스트 옵션명에서 수량 정보를 정규식으로 추출해 `{unit, unit_quantity, piece_count, pack_count, bonus_quantity, confidence, raw_match}` 스키마를 반환해야 한다(SHALL). 다음 7가지 패턴을 최소한 커버해야 한다.

1. `N개입` / `N롤` — 단순 개수
2. `용량 N개입` (예: `2L 12개입`) — 단위용량 × 개수
3. `NxM팩(총 K개입)` — 총량 병기 검증
4. `용량 X N팩` (예: `500g x 2팩`) — 곱연산
5. `대용량(세부)` (예: `1kg(500g x 2팩)`) — 괄호 안 세부, 중복 합산 금지
6. `증정 결합` (예: `3개 + 펌프 2개`) — 본품·증정 분리
7. `쉼표 결합` (예: `150g, 3개`) — 쉼표 구분자

단위 사전은 최소 `g/kg/mg/ml/l/cl/L`(중량·용량)과 `개/개입/입/롤/팩/세트/박스/봉/병/장/매`(개수계)를 포함해야 한다(SHALL).

#### Scenario: 단위용량 × 개수 패턴
- **WHEN** 옵션 텍스트 `"2L 12개입"` 을 파싱한다
- **THEN** `{unit: "ml", unit_quantity: 24000, piece_count: 12, pack_count: 1, bonus_quantity: 0, confidence: "rule", raw_match: "2L 12개입"}` 을 반환한다

#### Scenario: 곱연산 패턴
- **WHEN** 옵션 텍스트 `"500g x 2팩"` 을 파싱한다
- **THEN** `{unit: "g", unit_quantity: 1000, piece_count: 2, pack_count: 2, confidence: "rule", raw_match: "500g x 2팩"}` 을 반환한다

#### Scenario: 총량 병기 검증
- **WHEN** 옵션 텍스트 `"5개입 x 8팩(총 40개입)"` 을 파싱한다
- **THEN** `unit_quantity: 40` 으로 명시 총량을 우선 사용해 반환한다

#### Scenario: 괄호 세부는 중복 합산하지 않는다
- **WHEN** 옵션 텍스트 `"1kg(500g x 2팩)"` 을 파싱한다
- **THEN** `unit_quantity: 1000` (g 기준) 만 반환하고 괄호 안 500g×2 는 검증용으로만 사용한다

#### Scenario: 증정 분리
- **WHEN** 옵션 텍스트 `"3개 + 펌프 2개"` 를 파싱한다
- **THEN** `{piece_count: 3, bonus_quantity: 2, ...}` 으로 본품과 증정을 분리 반환한다

#### Scenario: 단위 사전에 없는 단위
- **WHEN** 옵션 텍스트에 매칭되는 단위가 없다
- **THEN** 파서는 `None`/폴백 트리거 신호를 반환한다

### Requirement: LLM 폴백 파싱

정규식 파서가 `None` 을 반환하거나 신뢰도 낮은 결과(예: `confidence: "low"` 지표)를 낼 때, 시스템은 LLM을 호출해 동일 스키마로 구조화 JSON 응답을 받아야 한다(SHALL). 기본 백엔드는 로컬 Ollama(`qwen2.5:7b`)이며, 로컬 불가 시 OpenAI `gpt-4o-mini` 로 폴백한다. 응답에는 `confidence: "llm"` 을 표기한다.

#### Scenario: 규칙 파서 실패 → LLM 폴백 성공
- **WHEN** 옵션 텍스트 `"스페셜 에디션 프리미엄 대용량 패키지"` 를 규칙 파서가 파싱하지 못한다
- **THEN** 시스템은 LLM에 JSON 스키마 응답을 요청해 수량 정보를 추출하고 `confidence: "llm"` 으로 표기해 반환한다

#### Scenario: LLM 호출 자체가 실패한다
- **WHEN** LLM 응답이 유효 JSON이 아니거나 호출이 타임아웃된다
- **THEN** `{confidence: "low", parse_error: "<reason>", raw_match: <원본>}` 를 반환하고 상위 계층에서 `unit_price: null` 처리된다

#### Scenario: 월 토큰 캡 초과
- **WHEN** `LLM_MONTHLY_TOKEN_CAP` 환경변수 한도에 도달했다
- **THEN** LLM 폴백을 비활성화하고 규칙 파서 결과만 반환하며 `confidence: "low"` 로 표기한다

### Requirement: 파싱 결과 이중 캐시

시스템은 파싱 결과를 Redis(단기)와 PostgreSQL `option_text_cache(text_hash PK, parsed_json, model_used, created_at)` 에 저장해 같은 텍스트의 중복 파싱을 막아야 한다(SHALL). 캐시 키는 정규화된 옵션 텍스트의 SHA-256 해시다.

#### Scenario: 동일 텍스트 재파싱 요청
- **WHEN** 이전에 파싱된 옵션 텍스트가 다시 요청된다
- **THEN** Redis 또는 Postgres 캐시에서 결과를 반환하고 파서/LLM 호출을 건너뛴다

#### Scenario: 캐시 무효화
- **WHEN** 파서 버전(`PARSER_VERSION`)이 올라가 `option_text_cache.parser_version` 과 다르다
- **THEN** 해당 엔트리를 무효화하고 재파싱을 수행한다
