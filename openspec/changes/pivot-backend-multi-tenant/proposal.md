## Why

현재 `lowest-price` 백엔드는 친구 3-5명용 비공개 도구로, `/scraper` Mac mini + `backend/app/collectors/` (Playwright·nodriver) 구조로 네이버·쿠팡을 직접 크롤링한다. 이 구조를 **B2B 소매점 조달 SaaS**로 피벗하려 할 때 다음 리스크가 확정적으로 터진다.

- **기술적 리스크**: 쿠팡 Akamai Bot Manager는 상용 트래픽 볼륨에서 곧바로 차단된다. 현재도 `c4a8b2b`에서 봇 차단 페이지 감지를 보강했지만, 스케일업 시 유지 불가.
- **법적 리스크**: 대법원 2017(잡코리아 vs 사람인)·2022(2021도1533) 판례로 공개 서비스에서의 경쟁사 DB 크롤링은 부정경쟁행위·데이터베이스권 침해로 확정 손해배상 대상이다. 네이버·쿠팡 이용약관 위반은 서비스 차단·계정 영구 정지의 직접 근거.
- **비즈니스 리스크**: 친구용 용도를 벗어나 유료 테넌트(소매점)에 크롤링 결과를 제공하면 "영업 목적 무단 수집"으로 판례상 가장 불리한 포지션.

피벗 방향은 **테넌트(소매점) 스코프의 인증된 ingestion client가 수집·정규화한 결과를 백엔드로 업로드**하는 구조다. 브라우저 확장·Tauri 데스크톱 앱은 optional/internal ingestion client일 뿐 canonical product surface가 아니다. 백엔드는 더 이상 크롤링하지 않고, 테넌트별 데이터 격리·OAuth 인증·발주 이력 관리·리포트 집계만 담당한다. 이를 위해 현재 단일 사용자 전제의 백엔드를 **multi-tenant**로 재설계해야 한다.

## What Changes

### 아키텍처 전환
- 백엔드 역할 재정의: 크롤링 오케스트레이터 → **테넌트 데이터 수신·정규화·저장·리포트 서비스**
- 모든 사용자 노출 데이터에 `tenant_id` 격리(row-level filter)
- OAuth 기반 인증(카카오·네이버) + JWT access/refresh 토큰 도입
- 소매점(`shops`) 단위로 발주 주문(`procurement_orders`)과 수집 결과(`procurement_results`)를 저장·조회

### 재활용 (REUSE, 약 800줄)
기존 코드 중 도메인 로직은 그대로 유지한다.
- `backend/app/parsers/regex_parser.py` (223줄), `unit_dictionary.py` (86줄), `unit_price.py` (71줄) — 입력 소스가 DOM 파싱 결과로 바뀌더라도 텍스트 파싱 로직은 동일
- `backend/app/services/ranking_service.py` (44줄), `shipping_policy.py` (61줄), `cache_service.py` (55줄)
- `backend/app/models/base.py`, `backend/app/models/option_cache.py`
- `backend/app/api/v1/router.py`, `backend/app/api/v1/search.py` (인증 미들웨어 추가)

### 수정 (MODIFY)
- `parsers/option_parser.py` — 입력이 크롤러 HTML이 아니라 클라이언트가 업로드한 DOM 파싱 결과
- `parsers/llm_parser.py` — Ollama는 이미 제거됨(OpenAI `gpt-4o-mini`만 유지)
- `services/quota_service.py` — 플랫폼별 일일 쿼터 → **테넌트별 월간 API 쿼터**
- `services/search_service.py` — 크롤링 오케스트레이션 제거, 테넌트가 업로드한 수집 결과 처리로 재설계
- `models/listing.py` — `tenant_id BIGINT NOT NULL` 외래키 추가
- `core/config.py` — OAuth 클라이언트 키, JWT 시크릿, 테넌트·구독 설정 추가
- `api/v1/router.py` — `Depends(get_current_tenant)` 미들웨어 적용

### 신규 (NEW)
- `backend/app/tenancy/` — tenants, shops, users 모델·서비스·라우터
- `backend/app/auth/` — 카카오/네이버 OAuth + JWT 발급·검증
- `backend/app/procurement/` — procurement_orders, procurement_results 모델·서비스·라우터
- `backend/app/core/security.py` — JWT 로직 (기존 UA 로테이션 코드는 삭제 대상 collectors와 함께 폐기)

### 폐기 (DISCARD, 약 825줄)
- `backend/app/collectors/` 전체 — `remote_scraper.py`, `naver_detail.py`, `coupang_detail.py`, `coupang.py`, `naver.py`, `http_client.py`, `rate_limiter.py`, `circuit_breaker.py`, `selectors.yaml`, `selectors_loader.py`, `base.py`
- `/scraper/` 디렉토리 (Mac mini 용 코드의 레포 내 버전)
- `backend/app/ui/streamlit_app.py` — 내부 테스트용. 외부 클라이언트(Tauri 데스크톱 앱)가 대체
- `backend/app/services/detail_cache_service.py` — 상세 페이지 캐시는 크롤링 전제. 클라이언트 업로드 구조에서는 불필요

## Capabilities

### New Capabilities
- `tenancy`: 테넌트·소매점·사용자 엔티티를 관리하고 row-level 격리 의존성을 제공한다. 플랜(`starter`/`pro`/`enterprise`)과 월간 API 쿼터를 관리한다.
- `auth-oauth`: 카카오·네이버 OAuth 2.0 로그인을 처리하고 JWT access/refresh 토큰을 발급·검증한다. FastAPI 의존성 주입으로 현재 테넌트를 식별한다.
- `procurement-orders`: 테넌트 소속 소매점이 생성한 발주 주문(SKU 리스트 + 메타)을 저장·조회한다.
- `procurement-results`: 클라이언트(브라우저 확장·Tauri 앱)가 업로드한 수집 결과(플랫폼·상품 데이터·절감액)를 저장·조회한다. 발주 주문과 N:1 관계.

### Modified Capabilities
- `product-search`: 크롤링 기반에서 **클라이언트 업로드 기반**으로 전환. `tenant_id` 필터를 추가하고, 검색어 기반 수집 오케스트레이션 대신 업로드된 결과를 랭킹·정렬해 반환.
- `listing-detail-collector`: 백엔드 스크래퍼 삭제. 스펙을 **클라이언트가 업로드한 DOM 파싱 결과 수신 API**로 재정의.
- `option-quantity-parser`: 입력 소스만 변경(크롤러 HTML → 클라이언트 업로드 텍스트). 로직·캐시 동일, 캐시 키에 `tenant_id` 네임스페이스 추가.
- `landed-unit-price`: 계산 로직 동일, 테넌트 단위 리포트 집계 시 `tenant_id` 기준 필터 추가.
- `search-api`: 모든 엔드포인트에 `Depends(get_current_tenant)` 적용. 응답 캐시 키에 `tenant_id` 포함.

### Deleted Capabilities
- `naver-crawling` (암묵적·별도 spec 없음, collectors/naver*.py) — 완전 폐기
- `coupang-crawling` (암묵적·별도 spec 없음, collectors/coupang*.py) — 완전 폐기
- `remote-scraper` (`/scraper/` Mac mini 연동) — 완전 폐기
- `streamlit-internal-ui` — Tauri 데스크톱 앱이 대체

## Impact

### 사용자
- **친구용 도구 사용자(= 본인 + 친구 몇 명)**: 기존 `/api/v1/search?q=...` 단일 검색 엔드포인트는 호환성 유지 불가. 피벗 시점에 읽기 전용으로 동결하거나 사용자에게 종료 공지 후 차단한다. 기존 DB 데이터는 버리고 깨끗한 schema로 시작한다(마이그레이션 없음).
- **신규 B2B 테넌트**: 카카오·네이버 OAuth로 가입 → 소매점 등록 → 발주 주문 등록 → 인증된 ingestion client 또는 내부 운영 도구로 결과 수집 → Noti-first 알림으로 조달 결과 수신.

### 코드베이스
- **삭제**: 약 825줄 (collectors 전체) + `/scraper/` 디렉토리 + `ui/streamlit_app.py` + `services/detail_cache_service.py` + 관련 테스트
- **신규**: `tenancy/`, `auth/`, `procurement/`, `core/security.py` (JWT) — 예상 약 1,200줄 (모델·서비스·라우터·테스트 포함)
- **수정**: `parsers/option_parser.py`, `services/search_service.py`, `services/quota_service.py`, `models/listing.py`, `core/config.py`, `api/v1/router.py`

### 의존성
- **추가**: `python-jose[cryptography]` (JWT), `httpx-oauth` 또는 카카오/네이버 SDK 래퍼, `passlib[bcrypt]` (local 패스워드 해시 예비)
- **제거**: `playwright`, `selectolax`, `curl_cffi`, `tenacity` 중 크롤링 전용 재시도 설정, `vcrpy`/`respx` 중 크롤러 모킹 전용 테스트 의존
- **유지**: `fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `redis`, `pydantic-settings`, `structlog`

### 인프라
- **Docker Compose**: `postgres:16`, `redis:7`, `backend` 유지. `streamlit`·`playwright-base` 이미지는 제거
- **환경변수 추가**: `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_ACCESS_TTL_MINUTES`, `JWT_REFRESH_TTL_DAYS`, `KAKAO_CLIENT_ID`, `KAKAO_CLIENT_SECRET`, `KAKAO_REDIRECT_URI`, `NAVER_OAUTH_CLIENT_ID`, `NAVER_OAUTH_CLIENT_SECRET`, `NAVER_OAUTH_REDIRECT_URI`, `DEFAULT_TENANT_API_QUOTA_MONTHLY`
- **환경변수 제거**: `NAVER_CLIENT_ID`/`NAVER_CLIENT_SECRET`(쇼핑 API 용도) — OAuth 용은 별도 키로 분리 재추가, `PLAYWRIGHT_CONCURRENCY`, `NAVER_RPM`, `COUPANG_RPM`, `SCRAPER_REMOTE_URL` 등 크롤링 전용 설정

### 법적·운영
- **법적 노출 제거**: 백엔드가 직접 크롤링하지 않음 → 잡코리아 판례 직접 적용 대상 아님. 테넌트가 로그인 세션에서 자기 트래픽으로 DOM을 보는 행위는 각 테넌트의 이용약관 문제로 분리된다(본 변경 범위 외 — 사용자 약관에 명시).
- **상용 배포 가능성**: B2B SaaS로 전환하므로 기존 "친구용 비공개" 제약은 해제된다. 대신 테넌트 온보딩·결제·SLA 가 영역 D·E 에서 별도 제안된다.

### Migration 전략
- **기존 데이터 버림**: 친구 3-5명만 사용 → 이관 가치 없음. `alembic downgrade base` 후 신규 리비전 생성.
- **schema 드롭 & 재생성**: 로컬 dev DB는 `docker compose down -v` 로 초기화.
- **기존 친구용 사용자 대응**: README·`.env.example` 상단에 "친구용 버전은 `main@c4a8b2b` 태그 이전에서 사용하세요" 고지.

### 타 영역 제안과의 연관
- **영역 B (Frontend Tauri)**: `pivot-noti-first-procurement` 이후 사용자-facing 제품 범위에서 제외된다. 내부 파서 QA·운영자 디버깅·optional ingestion 실험 도구로만 유지한다.
- **영역 C (Browser Extension)**: optional ingestion client 후보이며, Noti-first 알림 워크플로의 필수 구성요소가 아니다.
- **영역 D (Billing/Subscriptions)**: `tenants.plan` 컬럼과 `subscriptions` 테이블 FK 예약 — 본 스펙에서는 필드만 준비하고 실제 구독 로직은 영역 D 제안 책임.
- **영역 E (Admin/Ops)**: 관측성·백오피스. `tenants`·`procurement_orders` 읽기 전용 뷰가 전제.
