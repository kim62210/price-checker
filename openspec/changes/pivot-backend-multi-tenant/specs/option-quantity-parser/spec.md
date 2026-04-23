## MODIFIED Requirements

### Requirement: 정규식 기반 7패턴 파서

시스템은 자유 텍스트 옵션명에서 수량 정보를 정규식으로 추출해 `{unit, unit_quantity, piece_count, pack_count, bonus_quantity, confidence, raw_match}` 스키마를 반환해야 한다(SHALL). 입력 소스는 피벗 전 **크롤러가 fetch한 HTML 내 옵션 텍스트** 에서 피벗 후 **클라이언트(Tauri·브라우저 확장)가 업로드한 `procurement_results.product_data.options[].name` 텍스트** 로 변경된다. 파싱 로직과 7패턴 매칭은 동일하다.

#### Scenario: 클라이언트 업로드 옵션 텍스트 파싱
- **WHEN** `procurement_results` 업로드 처리 중 `product_data.options[].name = "2L 12개입"` 가 파서로 전달된다
- **THEN** 파서는 기존과 동일하게 `{unit: "ml", unit_quantity: 24000, piece_count: 12, pack_count: 1, bonus_quantity: 0, confidence: "rule", raw_match: "2L 12개입"}` 을 반환한다

#### Scenario: 7패턴 매칭 유지
- **WHEN** 본 스펙의 이전 버전(`add-lowest-price-mvp`)에서 정의된 7패턴(`N개입`·`용량 N개입`·`NxM팩`·`용량 X N팩`·`대용량(세부)`·`증정 결합`·`쉼표 결합`) 케이스가 입력된다
- **THEN** 파서는 이전 스펙의 모든 Scenario 를 동일하게 만족해야 한다 (회귀 방지)

### Requirement: LLM 폴백 파싱

정규식 파서가 `None` 또는 낮은 신뢰도 결과를 낼 때, 시스템은 LLM 을 호출해 동일 스키마로 구조화 JSON 응답을 받아야 한다(SHALL). LLM 백엔드는 **OpenAI `gpt-4o-mini` 단일 구성** 으로 통일한다 (기존 Ollama 폴백은 이전 릴리스에서 이미 제거됨). 응답에는 `confidence: "llm"` 을 표기한다.

#### Scenario: 규칙 파서 실패 → LLM 폴백 성공
- **WHEN** 옵션 텍스트 `"스페셜 에디션 프리미엄 대용량 패키지"` 를 규칙 파서가 파싱하지 못한다
- **THEN** 시스템은 OpenAI `gpt-4o-mini` 에 JSON 스키마 응답을 요청해 수량 정보를 추출하고 `confidence: "llm"` 으로 표기해 반환한다

#### Scenario: LLM 호출 자체가 실패한다
- **WHEN** LLM 응답이 유효 JSON 이 아니거나 호출이 타임아웃된다
- **THEN** `{confidence: "low", parse_error: "<reason>", raw_match: <원본>}` 를 반환하고 상위 계층에서 `unit_price: null` 처리된다

#### Scenario: 월 토큰 캡 초과
- **WHEN** `LLM_MONTHLY_TOKEN_CAP` 환경변수 한도에 도달했다
- **THEN** LLM 폴백을 비활성화하고 규칙 파서 결과만 반환하며 `confidence: "low"` 로 표기한다

### Requirement: 파싱 결과 이중 캐시

시스템은 파싱 결과를 Redis(단기)와 PostgreSQL `option_text_cache(text_hash PK, parsed_json, model_used, parser_version, tenant_id?, created_at)` 에 저장해 같은 텍스트의 중복 파싱을 막아야 한다(SHALL). 캐시 키는 정규화된 옵션 텍스트의 SHA-256 해시다. **`option_text_cache` 는 전역 캐시로 유지** 하되, 텔레메트리·감사 목적으로 `tenant_id` 컬럼을 참고 정보로 기록할 수 있다(선택).

#### Scenario: 동일 텍스트 재파싱 요청 (전역 캐시 히트)
- **WHEN** 테넌트 A 가 이전에 파싱한 옵션 텍스트를 테넌트 B 가 요청한다
- **THEN** 시스템은 전역 캐시(`option_text_cache`)에서 결과를 반환한다 (파싱 결과는 공개 텍스트 → 결정론적이므로 테넌트 격리 불필요)

#### Scenario: Redis 단기 캐시 키 네임스페이스
- **WHEN** Redis 에 파싱 결과를 임시 저장한다
- **THEN** 키는 `parse:option:{sha256}` 형식의 전역 네임스페이스를 사용한다 (Redis 캐시도 결정론적이므로 테넌트 분리 불필요)

#### Scenario: 캐시 무효화
- **WHEN** 파서 버전(`PARSER_VERSION`)이 올라가 `option_text_cache.parser_version` 과 다르다
- **THEN** 해당 엔트리를 무효화하고 재파싱을 수행한다
