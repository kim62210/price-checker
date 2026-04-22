## Context

- 사용자(본인과 친구 3-5명)는 네이버 스마트스토어와 쿠팡에서 같은 소매 제품을 비교 구매한다. 플랫폼별로 옵션 구성(용량·개수·팩·세트)과 배송비가 달라 **정말 개당 얼마가 싼지** 비교가 어렵다.
- 공식 API 한계(조사 보고서 `IMPLEMENTATION_PLAN.md` 반영):
  - 네이버 쇼핑 검색 API: `lprice`/`hprice`/`mallName` 등 대표가만 제공. 배송비·옵션별 가격 ❌. 쿼터 25,000/day, `start+display ≤ 1000`.
  - 쿠팡 Partners API: HMAC, Search 시간당 10회/건당 10개. 최종 승인(누적 판매 15만원) 필요. 옵션별 가격·실배송비 ❌.
  - 네이버 Commerce API / 쿠팡 Seller API: 판매자 본인 한정, 타사 조회 불가.
- 법적/윤리적 맥락:
  - 대법원 2017(잡코리아 vs 사람인), 2022(2021도1533): 공개 서비스는 데이터베이스권·부정경쟁행위·robots.txt 무시 리스크 큼.
  - 본 변경은 **친구용 비공개·저빈도**로 제한 → 이용약관 위반 가능성은 존재하나 실질 법적/운영 리스크는 낮다.
- 운영 환경: macOS 개발자 로컬(Docker Compose) + 필요 시 Fly.io 1-인스턴스 수준. 공개 도메인 노출 없음.

## Goals / Non-Goals

**Goals:**
- 검색어 1회로 네이버 스마트스토어와 쿠팡 양쪽의 후보 상품을 수집해 **개당 실가(`(옵션가 + 배송비) / 실수량`)** 오름차순 정렬된 JSON을 반환한다.
- 옵션 텍스트 7패턴 정규식 파서로 커버리지 85% 이상을 달성하고, 실패분은 LLM 폴백(OpenAI gpt-4o-mini 또는 로컬 Ollama)으로 처리한다.
- 저빈도 사용 전제로 요청 throttle·UA 로테이션·상세 캐시·재시도/백오프를 기본 내장한다.
- Docker Compose 원클릭 로컬 실행(Postgres + Redis + FastAPI + Streamlit UI)을 제공한다.
- pytest 테스트 커버리지 80% 이상을 유지한다.

**Non-Goals:**
- 공개 서비스화, 외부 사용자 인증, 수수료 수익 모델.
- Next.js 프론트엔드(Streamlit/Gradio 수준에서 멈춘다).
- 가격 히스토리 시계열 UI, 가격 변동 알림(Push/Email).
- pgvector 기반 canonical 상품 매칭(MVP는 플랫폼별 결과를 나란히 보여주는 수준).
- 11번가·G마켓·옥션·SSG 등 추가 플랫폼.
- 쿠팡 Partners 승인·API 사용(Post-MVP에 수익 모델 붙일 때).

## Decisions

### 1. 수집 경로: "API 우선 → 정적 HTML → 헤드리스 폴백" 3계층
- 네이버는 공식 쇼핑 검색 API로 후보 리스팅을 받고(배송비·옵션가 없음 → 상세 페이지 재수집), 스마트스토어 상세는 SPA라 Playwright 폴백 우선.
- 쿠팡은 파트너스 승인 전이라 Search 페이지(`www.coupang.com/np/search`)와 상세(`/vp/products/{id}`)를 저빈도 직접 fetch. Akamai 차단 시 Playwright 폴백.
- 대안(모두 스크래핑 or 모두 API)은 장단이 명확히 반대. 3계층이 실패 모드에서 가장 강건하고 저빈도에 적합.

### 2. HTTP 클라이언트: httpx (async, HTTP/2)
- 이유: FastAPI와 동일 런타임, 커넥션 풀링·재시도·타임아웃 제어 세밀. requests 대비 async 지원.
- 대안: aiohttp(러닝커브 ↑), curl_cffi(TLS 지문 위조 필요 시만 도입).

### 3. 렌더 폴백: Playwright (Python, async) + stealth 패치
- 이유: 스마트스토어 SPA·CAPTCHA, 쿠팡 Akamai 대응 필요. puppeteer 포크인 pyppeteer는 유지보수 정체.
- 동시성 제한: `asyncio.Semaphore(2)` — 개인 PC 리소스 보호.

### 4. HTML 파싱: selectolax (CPython 바인딩)
- 이유: BeautifulSoup 대비 최대 30배 빠름, 대량 리스트 파싱 유리. 간단한 CSS 선택자면 충분.
- 대안: lxml(괜찮지만 설치 풋프린트 큼), BeautifulSoup(가독성 좋으나 느림).

### 5. 데이터 저장: PostgreSQL 16 + Redis 7
- Postgres: 트랜잭션, `raw` JSONB 원본 보존, 옵션·상세·가격 스냅샷. SQLAlchemy 2.0 async + asyncpg + Alembic.
- Redis: Arq 브로커 + 캐시(검색 결과 TTL 10분, 상세 페이지 TTL 6시간) + 네이버 일일 쿼터 카운터(`INCR` + `EXPIREAT 00:00 KST`).

### 6. 태스크/스케줄: Arq
- 이유: asyncio 네이티브, Redis 단일 백엔드, FastAPI와 동일 런타임. 개인 프로젝트에 Celery는 과함.
- 크론은 Arq `cron_jobs`로 통합(APScheduler 별도 도입 안 함).

### 7. 파싱 전략: "정규식 1차 → LLM 폴백"
- 정규식 7패턴: `N개입`, `용량 N개입`, `NxM팩`, `용량 X N팩`, `대용량(세부)`, `증정 결합`, `쉼표 결합`. 한·영 단위 사전 병행.
- LLM 폴백: 기본 로컬 Ollama(`qwen2.5:7b`)로 토큰 비용 0, 장애/미설치 시 OpenAI `gpt-4o-mini`. 월 토큰 캡(`LLM_MONTHLY_TOKEN_CAP`) 초과 시 비활성화 + `parsing_confidence: low` 반환.
- 파싱 결과는 Redis + Postgres `option_text_cache(text_hash PK)` 이중 캐시.

### 8. 개당 실가 공식
- `unit_price = (option_price + shipping_fee_for_this_purchase) / unit_quantity`
- 기준단위 표시: Google Merchant 스키마 준용(`ml`/`g`/`ct`/`sheet`), `100ml`·`100g`·`1ct` 등 가독 단위로 환산.
- 배송비 무료 조건: 쿠팡 로켓 비회원은 **실결제액 19,800원 이상**(2026-04 정책), 네이버 스마트스토어는 셀러별 `free_threshold`.
- 수량 파싱 실패 시 `unit_price: null` + `unit_price_confidence: low` 로 명시 반환.

### 9. UI: Streamlit
- 이유: 개발 30분 내 내부용 대시보드 가능. Next.js 도입은 Post-MVP. Gradio도 무방하나 Streamlit이 표 렌더링에 유리.

### 10. Rate Control: 토큰 버킷 + 랜덤 jitter
- 플랫폼별 분당 한도 환경변수(`NAVER_RPM`, `COUPANG_RPM`)로 제한.
- 요청 사이 랜덤 sleep(0.5s–2s jitter)으로 기계적 패턴 완화.
- UA 로테이션은 Chrome/Safari/Firefox 데스크톱 10개 풀에서 랜덤 선택.

### 11. 탄력성 패턴
- httpx timeout: `connect=3, read=8, write=3, pool=5`.
- tenacity 재시도: `wait_exponential_jitter(initial=0.5, max=8), stop_after_attempt(3)`, 429/5xx만.
- 서킷브레이커: Redis에 `circuit:{platform}:state` (60초 open) 단순 구현.
- Partial failure: `asyncio.gather(..., return_exceptions=True)` + 응답 `sources` 메타에 각 플랫폼 상태 명시.

### 12. 관측성
- structlog + correlation_id 미들웨어.
- Sentry(무료 티어) + prometheus-fastapi-instrumentator(RED + 캐시 히트/LLM 폴백/쿼터 잔량 커스텀 메트릭).

## Risks / Trade-offs

- [네이버/쿠팡 HTML 구조 변경으로 셀렉터가 주기적으로 깨진다] → 셀렉터를 `collectors/selectors.yaml` 설정 파일로 분리, 수집 실패를 메트릭으로 감지, 실패 시 Playwright 폴백 자동 전환.
- [쿠팡 Akamai Bot Manager 차단] → 저빈도 사용 + UA 로테이션 + 랜덤 jitter 기본. 차단 감지 시 서킷브레이커 open 후 Playwright(stealth) 폴백. 반복 차단되면 사용자에게 해당 플랫폼 off 안내.
- [LLM 폴백 비용 폭주] → 월 토큰 캡 환경변수 + Postgres 이중 캐시 + 규칙 파서 커버리지를 85% 이상으로 유지. 캡 초과 시 규칙 파서만 동작.
- [옵션 텍스트 다양성 부족으로 규칙 커버리지 미달] → 실측 샘플 50+ 케이스 라벨링, 실패 케이스는 로그로 수집해 패턴 추가.
- [배송비 정책 복잡(묶음배송/쿠폰/회원가)] → MVP는 단순화: 상세 페이지에 명시된 기본 배송비만 사용, 회원/쿠폰 가격은 "참고" 수준. 응답에 `shipping_confidence`·`price_confidence` 필드로 불확실성 노출.
- [친구용 전제가 느슨해져 공개 배포될 경우 법적 노출] → 프론트에 "본 서비스는 비공개 친구용입니다. 외부 공유 금지" 문구 고정, README에 Scope-In/Out 명시.
- [쿠팡 정책 변경(2026-04 무료배송 19,800원 기준 등)] → 배송비 정책을 `services/shipping_policy.py` 한 곳에서 관리해 변경 시 단일 파일 수정.

## Migration Plan

신규 프로젝트이므로 마이그레이션 없음. 초기 배포 절차:
1. `.env` 파일 생성 (`NAVER_CLIENT_ID`/`SECRET` 필수)
2. `docker compose up -d` → Postgres, Redis, FastAPI, Streamlit 기동
3. `alembic upgrade head` → 스키마 초기화
4. `curl http://localhost:8000/api/v1/search?q=코카콜라` 로 스모크 테스트
5. Streamlit UI 접속 `http://localhost:8501`

롤백: `docker compose down -v` 로 컨테이너·볼륨 제거.

## Open Questions

- 네이버 쇼핑 API 이용 시 로고/출처 표기 의무 범위 (Streamlit UI에 "Powered by Naver" 로고 표기 필요 여부) — `[교차검증 필요]` 네이버 개발자센터 이용약관 직접 확인
- LLM 폴백 기본값을 로컬 Ollama(설치 필수)로 할지 OpenAI API(키 필수)로 할지 — 1차는 **Ollama 우선, OpenAI 폴백**으로 확정, 실측 품질에 따라 재조정
- 쿠팡 상세 페이지 차단 빈도가 실제로 얼마나 되는지는 구현 후 관측 필요 → 서킷브레이커 임계치 실측 기반 튜닝
- 배송비 추정 불가 상품에 대해 기본값 3,000원을 적용할지, 상품 목록에서 제외할지 — 1차는 **포함 + `shipping_confidence: estimated`** 로 노출
