## 1. 프로젝트 스캐폴드

- [ ] 1.1 `backend/pyproject.toml` 생성 (Python 3.12, 의존성: fastapi, uvicorn[standard], httpx[http2], selectolax, playwright, sqlalchemy[asyncio], asyncpg, alembic, pydantic, pydantic-settings, redis, arq, tenacity, structlog, prometheus-fastapi-instrumentator, pytest, pytest-asyncio, pytest-cov, vcrpy, respx, streamlit)
- [ ] 1.2 `backend/app/__init__.py`, `backend/app/main.py` (FastAPI 앱 팩토리, CORS, 미들웨어 슬롯)
- [ ] 1.3 `.env.example` (NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, DATABASE_URL, REDIS_URL, OPENAI_API_KEY, OLLAMA_BASE_URL, NAVER_RPM, COUPANG_RPM, SEARCH_CACHE_TTL_SECONDS, DETAIL_CACHE_TTL_SECONDS, LLM_MONTHLY_TOKEN_CAP, PLAYWRIGHT_CONCURRENCY, PARSER_VERSION)
- [ ] 1.4 `.gitignore`, `.dockerignore`
- [ ] 1.5 `README.md` 초안 (프로젝트 목적·친구용 비공개 안내·실행 절차)

## 2. Core 인프라

- [ ] 2.1 `backend/app/core/config.py` — pydantic-settings `Settings` 클래스
- [ ] 2.2 `backend/app/core/logging.py` — structlog 설정, correlation_id 프로세서
- [ ] 2.3 `backend/app/core/exceptions.py` — 커스텀 예외 + `{detail, code}` 표준 핸들러
- [ ] 2.4 `backend/app/core/middleware.py` — correlation_id 주입 미들웨어
- [ ] 2.5 `backend/app/core/security.py` — UA 로테이션 풀 + 헤더 빌더

## 3. DB/캐시 계층

- [ ] 3.1 `backend/app/db/session.py` — async SQLAlchemy 세션 팩토리
- [ ] 3.2 `backend/app/models/base.py` — `DeclarativeBase`
- [ ] 3.3 `backend/app/models/listing.py` — `Listing`, `Option`, `PriceQuote` 테이블
- [ ] 3.4 `backend/app/models/option_cache.py` — `OptionTextCache(text_hash PK, parsed_json, model_used, parser_version, created_at)`
- [ ] 3.5 `backend/app/db/migrations/` — Alembic 초기화 + 첫 리비전
- [ ] 3.6 `backend/app/services/cache_service.py` — Redis cache-aside 헬퍼 (get/set/del, TTL)
- [ ] 3.7 `backend/app/services/quota_service.py` — 네이버 일일 쿼터 카운터 (`INCR` + 익일 00:00 KST `EXPIREAT`)

## 4. 수집기(Collectors)

- [ ] 4.1 `backend/app/collectors/base.py` — `Collector` ABC (`async def search`, `async def fetch_detail`)
- [ ] 4.2 `backend/app/collectors/naver.py` — 네이버 쇼핑 API 호출, tenacity 재시도, 쿼터 카운터 통합
- [ ] 4.3 `backend/app/collectors/coupang.py` — 쿠팡 검색 페이지 httpx fetch + selectolax 파싱
- [ ] 4.4 `backend/app/collectors/selectors.yaml` — 플랫폼별 CSS 선택자 외부화
- [ ] 4.5 `backend/app/collectors/rate_limiter.py` — 플랫폼별 분당 토큰 버킷 + 랜덤 jitter
- [ ] 4.6 `backend/app/collectors/playwright_runner.py` — 헤드리스 폴백 + stealth 패치 + 세마포어

## 5. 상세 페이지 수집

- [ ] 5.1 `backend/app/collectors/naver_detail.py` — 스마트스토어 상세 (Playwright 우선)
- [ ] 5.2 `backend/app/collectors/coupang_detail.py` — 쿠팡 상세 정적 파싱 + Playwright 폴백
- [ ] 5.3 `backend/app/services/detail_cache_service.py` — 상세 응답 Redis 캐시 (TTL 6시간, `force_refresh` 지원)
- [ ] 5.4 `backend/app/services/shipping_policy.py` — 플랫폼·셀러별 배송비 추정(쿠팡 19,800원 임계치, 스마트스토어 `free_threshold`)

## 6. 옵션/수량 파서

- [ ] 6.1 `backend/app/parsers/unit_dictionary.py` — 한·영 단위 사전 + 환산 계수
- [ ] 6.2 `backend/app/parsers/regex_parser.py` — 7패턴 정규식 구현 (`N개입`·`용량 N개입`·`NxM팩`·`용량 X N팩`·`대용량(세부)`·`증정 결합`·`쉼표 결합`)
- [ ] 6.3 `backend/app/parsers/llm_parser.py` — Ollama 기본 + OpenAI 폴백, JSON schema 강제, 월 토큰 캡 체크
- [ ] 6.4 `backend/app/parsers/option_parser.py` — 규칙→LLM 폴백 오케스트레이터 + 이중 캐시

## 7. 개당 실가 계산

- [ ] 7.1 `backend/app/parsers/unit_price.py` — `unit_price = (price + shipping_fee) / unit_quantity`, 기준단위 환산(100g/100ml/1ct), null 처리
- [ ] 7.2 `backend/app/services/ranking_service.py` — 결과 정렬 + `comparable_group` 분류

## 8. 오케스트레이션 + API

- [ ] 8.1 `backend/app/schemas/search.py` — `SearchRequest`, `SearchResponse`, `ResultItem`, `Sources` (Pydantic v2)
- [ ] 8.2 `backend/app/services/search_service.py` — 병렬 수집(`asyncio.gather(return_exceptions=True)`) → 상세 수집 → 파싱 → 실가 계산 → 랭킹
- [ ] 8.3 `backend/app/api/v1/search.py` — `GET /api/v1/search` + response_model + cache-aside 데코레이터
- [ ] 8.4 `backend/app/api/v1/health.py` — `/health/live`, `/health/ready` (Postgres·Redis 핑)
- [ ] 8.5 `backend/app/api/v1/router.py` — `APIRouter` 집계
- [ ] 8.6 `backend/app/main.py` 갱신 — 라우터 등록, Sentry 초기화, Prometheus instrumentator, 예외 핸들러

## 9. Streamlit UI

- [ ] 9.1 `backend/app/ui/streamlit_app.py` — 검색어 입력 → 백엔드 `/api/v1/search` 호출 → 결과 표(플랫폼·가격·배송비·실수량·단위가) + CSV 다운로드
- [ ] 9.2 Streamlit 상단에 "비공개 친구용, 외부 공유 금지" 배너 고정

## 10. Docker / Dev Ops

- [ ] 10.1 `infra/docker-compose.yml` — postgres:16, redis:7, backend, streamlit, (선택) ollama
- [ ] 10.2 `backend/Dockerfile` — 멀티스테이지(builder + runtime), slim-bookworm, playwright deps
- [ ] 10.3 `Makefile` — `make dev`, `make test`, `make lint`, `make migrate`
- [ ] 10.4 로컬 스모크 스크립트 `scripts/smoke_search.sh` — `curl` 기반 기본 체크

## 11. 테스트

- [ ] 11.1 `backend/tests/conftest.py` — 공통 fixture (AsyncClient, DB 트랜잭션 rollback, Redis 격리)
- [ ] 11.2 `backend/tests/test_parsers/` — 정규식 파서 50+ 케이스 parametrize (한·영·숫자 혼용)
- [ ] 11.3 `backend/tests/test_parsers/test_llm_parser.py` — Ollama/OpenAI 호출 모킹, JSON 스키마 검증
- [ ] 11.4 `backend/tests/test_parsers/test_unit_price.py` — 환산·null·무료배송 조건
- [ ] 11.5 `backend/tests/test_collectors/test_naver.py` — vcrpy/respx 기반 API 모킹, 쿼터 소진·재시도·UA
- [ ] 11.6 `backend/tests/test_collectors/test_coupang.py` — respx 모킹, Akamai 차단·서킷브레이커·파싱
- [ ] 11.7 `backend/tests/test_services/test_search_service.py` — partial failure, 병렬 호출, 랭킹
- [ ] 11.8 `backend/tests/test_api/test_search_endpoint.py` — AsyncClient 통합 테스트, 캐시 히트, 422/502/504
- [ ] 11.9 `backend/tests/test_api/test_health.py` — live/ready 상태
- [ ] 11.10 `pytest --cov` 으로 커버리지 80% 이상 확인

## 12. 문서/마무리

- [ ] 12.1 `README.md` 최신화 — 설치·실행·환경변수·API 사용 예시·법적 고지 (친구용 비공개)
- [ ] 12.2 `backend/app/core/config.py` 의 모든 환경변수를 `README.md`와 `.env.example` 에 동기화
- [ ] 12.3 IMPLEMENTATION_PLAN.md 의 "교차검증 필요" 체크리스트를 README 하단에 옮겨 실행 전 점검 안내
