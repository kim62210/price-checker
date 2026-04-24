# 네이버 스마트스토어 / 쿠팡 최저가 비교 서비스 — 구현 계획

> 조사일: 2026-04-22
> 기준 디렉토리: `/Users/adminstrator/Desktop/hyungjoo-drb/personal/lowest-price`
> 상태: **역사 문서**. 현재 제품 방향은 `openspec/changes/pivot-noti-first-procurement/`가 supersede한다. 이 문서는 초기 API-first 검색 서비스 조사와 제약 기록으로만 참고한다.

---

## 1. 서비스 목표

사용자가 특정 제품을 검색하면, 네이버 스마트스토어와 쿠팡에서 판매 중인 상품을 수집하고, **옵션 텍스트로부터 실 수량을 역파싱**하여 **배송비 포함 단위당 실가(원/100ml·원/100g·원/개)** 로 정렬해 제시한다.

---

## 2. 조사로 확정된 핵심 제약

### 2-1. 공식 API는 배송비·옵션별 가격을 제공하지 않는다

| 플랫폼 | 공식 API | 가격 | 배송비 | 옵션별 가격 | 제한 |
|---|---|---|---|---|---|
| 네이버 | 쇼핑 검색 API (`openapi.naver.com/v1/search/shop.json`) | `lprice`, `hprice` | ❌ | ❌ | **25,000 req/day**, start+display ≤ 1000 |
| 쿠팡 | Partners Open API (`api-gateway.coupang.com/v2/providers/affiliate_open_api/...`) | `productPrice` (대표가 1개) | ❌ (`isFreeShipping` boolean만) | ❌ | **Search 시간당 10회, 건당 최대 10개** |
| 네이버 | Commerce API (판매자용) | 옵션별 O | O | O | **판매자 본인 스토어 한정** — 타사 조회 불가 |
| 쿠팡 | Seller Open API | 옵션별 O | O | O | **판매자 본인 한정** |

**결론**: 타사 상품의 "옵션별 실제 배송비·실제 판매가"는 공식 API로 확보 불가능.

### 2-2. 크롤링은 법적·기술적 리스크가 높다

- 네이버: 2024-03-27 "비정상적/기계적 접근 시스템적 차단" 공지. 자체 봇 차단 시스템(SPA + CAPTCHA + IP Rate Limit + 내부 API 빈번 변경).
- 쿠팡: `robots.txt`가 **일반 봇을 명시적으로 Disallow** (`User-agent: * Disallow: /`) + Akamai Bot Manager 사용.
- 대법원 2017 (잡코리아 vs 사람인): 무단 크롤링 → 데이터베이스권 침해 + 부정경쟁행위 (1억 9800만원 배상).
- 대법원 2022 (2021도1533 여기어때): "객관적 보호조치가 있으면 형사 책임 가능" — 쿠팡의 robots.txt는 객관적 보호조치에 해당.

### 2-3. 쿠팡 Partners 승인 조건

- 누적 판매 실적 **15만원 이상** 도달 시 자동 심사 → 승인. 개인·사업자 모두 가입 가능.
- 승인 전에는 API 사용 불가. **실제 운영 전에 파트너스 가입 + 일정 기간 운영으로 승인 확보 필요**.

### 2-4. 단위가격 표시제 의무화 (2026-04-07 시행)

- 연간 거래액 10조 원 이상 온라인몰(쿠팡·네이버플러스스토어)은 114개 품목 단위가격 표시 의무.
- 서비스의 "단위당 실가" 표시는 기본값에 가까움 → 차별화 포인트는 **다(多) 플랫폼 비교** + **옵션 텍스트 역파싱 정확도**에 있다.

---

## 3. 설계 원칙: "API-First + 정직한 한계 표시"

1. **API 우선 경로 (MVP)**
   - 네이버 쇼핑 검색 API + 쿠팡 Partners API만 사용.
   - 응답 필드로 계산 가능한 수준(대표가 + 무료배송 여부 + 옵션명 텍스트)까지만 가공.
   - UI/응답에는 **"배송비는 상품 상세에서 확정됩니다"** 문구 명시 (공정위 표시광고 이슈 대응 포함).

2. **헤드리스 폴백 경로 (Post-MVP, 옵셔널)**
   - 필요 시에만 Playwright로 상세 페이지 접근 → 배송비·옵션가 확정.
   - 법적 리스크 및 안티봇 대응 비용 크므로, 자기 계정으로 로그인 세션만 소규모 사용 등 범위 엄격 제한.

3. **옵션 텍스트 파서가 가치의 핵심**
   - 공식 API가 옵션명을 구조화하지 않기 때문에, `"500g x 2팩"`, `"5개입 x 8팩(총40개입)"` 같은 자유 텍스트로부터 수량을 추출하는 **정규식 + LLM 폴백** 파이프라인이 서비스 차별점.

---

## 4. MVP 범위

### Scope In (10영업일 목표)
1. `GET /api/v1/search?q=<keyword>&limit=<n>` 단일 엔드포인트
2. 네이버 쇼핑 API / 쿠팡 Partners API 병렬 호출 (`asyncio.gather(return_exceptions=True)`)
3. 옵션 텍스트 정규식 파서 (7가지 패턴, 커버리지 85% 목표)
4. 단위당 실가 계산 (`unit_price = (price + shipping_est) / unit_qty`, 기준단위: Google Merchant 스키마)
5. Redis cache-aside (TTL 10분)
6. 네이버 일일 쿼터 카운터 (Redis `INCR` + `EXPIREAT 00:00 KST`)
7. PostgreSQL 저장 (원본 raw JSONB + 정규화 데이터)
8. partial failure 허용 (`sources: {naver: "ok", coupang: "error:..."}`)
9. pytest + 구조화 로깅 + Sentry

### Scope Out (Post-MVP)
- Next.js 프론트엔드
- pgvector 기반 상품 매칭 (MVP는 규칙 기반 정규화만)
- Playwright 폴백 수집
- 가격 히스토리 / 알림
- LLM 폴백 파싱 (1차는 정규식만, stub만 구현)
- 사용자 인증

---

## 5. 아키텍처

```
사용자 → FastAPI (/api/v1/search)
          │
          ├─ Redis 캐시 (TTL 10분) ── HIT → 즉시 응답
          │
          └─ MISS: asyncio.gather
               ├─ 네이버 쇼핑 API (httpx, X-Naver-Client-Id/Secret)
               └─ 쿠팡 Partners API (httpx, HMAC-SHA256)
          │
          ↓ 정규화 (옵션 텍스트 파싱 → 단위 환산)
          ↓ 단위당 실가 계산
          ↓ 정렬 + partial-failure 머지
          ↓ PostgreSQL 저장 (raw JSONB + 파싱 결과)
          ↓
          JSON 응답
```

---

## 6. 데이터 모델

```sql
-- 정규화된 상품 (플랫폼 중립, Post-MVP에서 pgvector 매칭에 사용)
canonical_products (id, brand, maker, canonical_name, gtin, category[], embedding vector(768), updated_at)

-- 플랫폼별 리스팅 (Canonical 1 : Listing N)
listings (id, canonical_product_id FK, platform, seller_id, platform_product_id, url, raw_title, fetched_at)

-- 옵션 (Listing 1 : Option N)
options (id, listing_id FK, platform_option_id, attrs jsonb, parsed jsonb, price, stock, usable)

-- 가격 스냅샷 (시계열, append-only)
price_quotes (id, option_id FK, captured_at, price, discount_price, shipping_fee, total_price,
              unit_qty, unit_price, unit_base jsonb, source_url, fetch_method)
```

### 6-1. 옵션 파싱 결과(`options.parsed` JSONB) 스키마
```json
{
  "unit": "ml",               // g|kg|ml|l|ct|sheet|cm|m|sqm (Google Merchant 준용)
  "unit_quantity": 24000,      // 기준단위 환산 총량 (2L × 12 = 24,000 ml)
  "piece_count": 12,           // 낱개
  "pack_count": 1,             // 팩
  "bonus_quantity": 0,         // 증정분
  "confidence": "rule",        // rule | llm | manual
  "raw_match": "2L 12개입"
}
```

### 6-2. 옵션 텍스트 7가지 패턴 (조사 기반)
1. `N개입` / `N롤` — 단순 개수
2. `용량 N개입` (`2L 12개입`, `150g 3개`) — 단위용량 × 개수
3. `NxM팩` (`5개입 x 8팩(총40개입)`) — 총계 병기 검증
4. `용량 X N팩` (`500g x 2팩`) — 곱연산
5. `대용량(세부)` (`1kg(500g x 2팩)`) — 괄호 안 세부, 중복 아님
6. `증정 결합` (`3개 + 펌프 2개`) — 본품/증정 분리
7. `쉼표 결합` (`150g, 3개`) — 쉼표 구분자

---

## 7. 기술 스택

### 백엔드
- Python 3.12+, FastAPI (async), uvicorn+uvloop
- `httpx` (HTTP/2 async), `selectolax`, `tenacity`
- SQLAlchemy 2.0 async + asyncpg + Alembic
- PostgreSQL 16 (+ pgvector, Post-MVP 매칭)
- Redis 7 (cache + Arq 큐, Post-MVP)
- pydantic v2 + pydantic-settings + structlog
- pytest + pytest-asyncio + httpx.AsyncClient + vcrpy

### 프론트 (Post-MVP)
- Next.js 15 App Router + TypeScript strict
- Tailwind + shadcn/ui + next-intl (i18n 규칙 준수: `messages/ko.json`, `messages/en.json`)

### 인프라
- 로컬: Docker Compose (postgres + redis + backend)
- 배포: Fly.io (backend) + Supabase (postgres+pgvector) + Upstash Redis + Vercel (frontend)
- 관측: Sentry + prometheus-fastapi-instrumentator

---

## 8. 디렉토리 구조

```
lowest-price/
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py
│   │   ├── core/           # config, logging, security(HMAC), exceptions
│   │   ├── api/v1/          # search, products, health
│   │   ├── collectors/      # base, naver, coupang, (playwright_runner post-MVP)
│   │   ├── parsers/         # regex_parser, llm_parser(stub), shipping_parser, unit_price
│   │   ├── services/        # search_service, matching_service, cache_service, quota_service
│   │   ├── models/          # SQLAlchemy 2.0
│   │   ├── schemas/         # Pydantic v2
│   │   ├── db/              # session, migrations
│   │   └── workers/         # (Post-MVP: arq_settings, tasks)
│   └── tests/
├── frontend/                # Post-MVP
├── infra/
│   └── docker-compose.yml
├── .env.example
├── README.md
└── IMPLEMENTATION_PLAN.md   # 이 파일
```

---

## 9. MVP 로드맵 (10영업일)

### Week 1 — 백엔드 스켈레톤 + 수집 + 파싱
| 일 | 작업 |
|---|---|
| Day 1 | 리포 init, `pyproject.toml`, `docker-compose.yml`(postgres+redis), `.env.example`, FastAPI `main.py` + `/health`, structlog, pytest bootstrap |
| Day 2 | `core/config.py` (pydantic-settings), `db/session.py` (async SQLAlchemy), 초기 모델 + Alembic migration, `cache_service.py` (redis.asyncio) |
| Day 3 | `collectors/naver.py` + vcrpy 단위테스트, `quota_service.py` (Redis 카운터 + 익일 00시 만료) |
| Day 4 | `collectors/coupang.py` (HMAC-SHA256) + 테스트, `collectors/base.py` ABC, `httpx.AsyncClient` DI |
| Day 5 | `parsers/regex_parser.py` (7패턴 + 한·영 단위 사전) + pytest parametrize 50+ 케이스, `parsers/unit_price.py` |

### Week 2 — 오케스트레이션 + 캐시 + 배포
| 일 | 작업 |
|---|---|
| Day 6 | `services/search_service.py` (`asyncio.gather(return_exceptions=True)` 병렬, partial failure 스키마) |
| Day 7 | `api/v1/search.py` 라우트 + `response_model` + cache-aside 데코레이터, AsyncClient 통합테스트 |
| Day 8 | Sentry, tenacity 재시도, 간이 서킷브레이커, `{detail, code}` 에러 핸들러 표준화 |
| Day 9 | 멀티스테이지 Dockerfile, `fly.toml`, Supabase/Upstash 프로비저닝 |
| Day 10 | README, 프로덕션 시드 테스트, SLI 대시보드 초기화, 회고 + 백로그 |

### Done Definition
- `curl https://<staging>/api/v1/search?q=코카콜라` 이 **1초 이내**(캐시 미스)로 네이버+쿠팡 결과를 단위가 오름차순 정렬해 반환
- 한쪽 플랫폼 장애 시 200 응답 + `sources`에 실패 원인 명시
- 규칙 파서 라벨 데이터 기준 **커버리지 85%** 이상
- 일일 네이버 쿼터 24,000회 이상 넘지 않도록 기록/차단

---

## 10. 구현 전 재확인이 필요한 항목 `[교차검증 필요]`

| # | 항목 | 방법 |
|---|---|---|
| 1 | 네이버 쇼핑 API `productType` 숫자 코드 매핑 | `developers.naver.com/docs/serviceapi/search/shopping/shopping.md` 직접 확인 |
| 2 | 네이버 검색 API 이용 시 로고/출처 표기 의무 | 네이버 개발자센터 이용약관 |
| 3 | 쿠팡 Partners `productPrice`의 기준 (일반가 vs 와우가) | Partners 공식 문서 + 실제 호출 검증 |
| 4 | Partners API Search 외 엔드포인트별 개별 rate limit | Partners 가이드 PDF (이미지) OCR |
| 5 | Partners 약관상 "가격비교 서비스" 허용 범위 | Partners 이용 가이드 PDF |
| 6 | 쿠팡 Partners 승인 상태 (누적 15만원 조건) | 본인 계정 확인 |
| 7 | 로켓배송 비회원 유료 배송비 실제 금액 | 실제 상품 페이지 샘플링 |
| 8 | `jhgan/ko-sroberta-multitask` 모델 카드 | `huggingface.co/jhgan/ko-sroberta-multitask` |

---

## 11. 법적·윤리적 체크리스트

- [ ] 네이버 검색 API 인증 키 발급 및 ToS 확인
- [ ] 쿠팡 Partners 계정 가입 및 승인 프로세스 진행
- [ ] API 링크에 Partners `productUrl` 그대로 사용 (수수료 귀속)
- [ ] 서비스 내 "가격·배송비는 최종 쿠팡/네이버 페이지에서 다를 수 있음" 고정 문구
- [ ] 크롤링 대체 경로는 **사용자가 직접 상세 페이지로 이동**하도록 UX 설계
- [ ] 서비스 약관/개인정보처리방침 준비 (공개 전)

---

## 12. 다음 단계 선택지

**A. 이 계획대로 OpenSpec propose 작성** → `/opsx:propose` → Phase 3 구현 착수
**B. 계획을 수정·보강** (예: 쿠팡 Partners 대신 네이버 단독 MVP, Playwright 폴백 포함 등) 후 OpenSpec
**C. 먼저 네이버 키 + 쿠팡 Partners 가입 진행** → 접근 가능 확인된 후 착수
**D. 다른 방향으로 재검토** (예: 사용자가 직접 URL을 넣으면 해당 URL만 파싱하는 "URL-input" 단순 모드부터 시작)
