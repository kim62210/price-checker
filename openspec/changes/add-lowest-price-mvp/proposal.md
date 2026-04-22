## Why

친구 몇 명이 네이버 스마트스토어와 쿠팡에서 같은 소매 제품을 찾을 때, 상품마다 옵션 구성(용량·개수)과 배송비가 제각각이라 **"정말 어떤 게 가장 싸냐?"** 를 비교하려면 각 상세 페이지를 일일이 열어야 한다. 공식 API는 대표가만 제공하고 배송비·옵션별 가격은 포함하지 않으므로, 검색 결과 전반을 자동 수집·정규화해 **배송비 포함 + 실 수량 기준 개당 실가**로 정렬해주는 친구용 비공개 도구가 필요하다.

## What Changes

- 새로운 백엔드 서비스 `lowest-price` 를 Python 3.12 + FastAPI로 구축한다.
- 단일 검색 엔드포인트 `GET /api/v1/search?q=<keyword>&limit=<n>` 을 제공한다.
- 네이버 쇼핑 검색 API와 쿠팡 검색·상세 페이지를 병렬로 수집한다.
- 후보 상품마다 상세 페이지를 폴링해 옵션별 가격·배송비·옵션 텍스트를 확보한다.
- 옵션 텍스트 7가지 패턴(`N개입`·`용량 N개입`·`NxM팩`·`용량 X N팩`·`대용량(세부)`·`증정 결합`·`쉼표 결합`)을 정규식으로 파싱하고, 실패 시 LLM으로 폴백한다.
- 개당 실가 `(옵션가 + 배송비) / 실수량` 을 계산해 오름차순 정렬 JSON을 반환한다.
- Redis 기반 캐시 + 요청 throttle + 일일 쿼터 카운터 + User-Agent 로테이션으로 봇 탐지/한도 초과를 방지한다.
- 내부 확인용 Streamlit UI를 번들한다(Next.js 프론트엔드는 Scope Out).
- Docker Compose로 로컬 원클릭 실행을 제공한다(postgres + redis + backend + streamlit).
- pytest 기반 테스트로 커버리지 80% 이상을 유지한다.

## Capabilities

### New Capabilities
- `product-search`: 검색어를 받아 네이버 쇼핑 API와 쿠팡 검색 페이지에서 후보 상품 리스팅을 수집한다.
- `listing-detail-collector`: 리스팅 식별자로 상세 페이지를 폴링해 옵션별 가격·배송비·옵션명 텍스트를 확보한다.
- `option-quantity-parser`: 자유 텍스트 옵션명에서 단위(ml/g/ct 등)·총 수량·낱개·팩 수를 역파싱한다.
- `landed-unit-price`: 옵션 가격과 배송비, 파싱된 수량으로 개당 실가를 계산하고 오름차순 정렬한다.
- `search-api`: FastAPI 라우터를 통해 위 파이프라인을 오케스트레이션하고 partial failure를 포함한 JSON 응답을 반환한다.

### Modified Capabilities
- (없음 — 신규 프로젝트)

## Impact

- **신규 코드**: `backend/app/` 전체 패키지 (collectors, parsers, services, api, db, workers, schemas)
- **의존성**: fastapi, uvicorn[standard], httpx[http2], selectolax, playwright, sqlalchemy[asyncio], asyncpg, alembic, pydantic, pydantic-settings, redis, arq, tenacity, structlog, prometheus-fastapi-instrumentator, pytest, pytest-asyncio, vcrpy, streamlit (UI 전용)
- **외부 API 키**: `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` (필수), `OPENAI_API_KEY` 또는 로컬 Ollama (LLM 폴백, 선택)
- **인프라**: PostgreSQL 16, Redis 7, Docker Compose 로컬 실행
- **법적 제약**: 친구용 비공개 저빈도 사용으로 한정. 공개 서비스화·상용 배포는 본 변경 범위 외.
- **파일**: `openspec/changes/add-lowest-price-mvp/` 아래 4개 아티팩트, 프로젝트 루트에 `backend/`, `infra/`, `.env.example`, `README.md` 신설
