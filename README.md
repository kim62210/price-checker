# lowest-price

B2B 조달 결과 알림 백엔드 (**멀티테넌트 피벗 완료, Noti-first 전환 진행 중**).

테넌트별 발주 이력과 업로드된 상품 옵션 데이터를 기반으로 "배송비 포함 개당 실가"를 계산하고, 사용자가 별도 UI를 열지 않아도 카카오 알림톡·SMS fallback으로 조달 결과와 재확인 필요 상태를 전달하는 방향으로 전환 중이다.

> **피벗 완료**: `openspec/changes/pivot-backend-multi-tenant/` 변경 스펙의 Wave 1~4 구현이 모두 반영됐다. 크롤링 기반 MVP 에서 JWT + 카카오/네이버 OAuth 인증·멀티테넌트·조달 업로드·테넌트 스코프 검색 구조로 전환됐다.
>
> **신규 제품 방향**: `openspec/changes/pivot-noti-first-procurement/` 변경 스펙에 따라 설치형 Tauri 앱은 중단·제거됐다. 사용자-facing 표면은 카카오 알림톡 + SMS/LMS fallback이며, 운영자용 화면은 별도 `ops-admin/` 웹 백오피스로 관리한다.

---

## 빠른 시작

```bash
cp .env.example .env
# 최소 DATABASE_URL / REDIS_URL / JWT_SECRET 을 채운다
# 카카오/네이버 OAuth 로 로그인하려면 OAuth 시크릿도 함께 설정

make install
make migrate
make dev             # Docker Compose 로 postgres/redis/backend 기동
# 또는
make dev-api         # 로컬 uvicorn 만
```

- API 기본 주소: `http://localhost:8000`
- 헬스 체크: `curl http://localhost:8000/health/live`


## 제품 방향: Noti-first 조달 알림

신규 수요조사 결과, 사장님이 별도 데스크톱 앱에 접속해 비교표를 탐색하는 방식보다 조달 결과·견적 완료·재확인 필요 상태를 카카오톡/SMS로 즉시 받아보는 방식의 효용이 더 높다고 판단했다. 따라서 MVP의 사용자-facing 흐름은 다음을 우선한다.

- 조달 결과·견적 완료·발주 상태: 카카오 알림톡
- 카카오 미도달/실패: SMS/LMS fallback
- 가격 리마인더·프로모션성 메시지: 명시적 마케팅 동의가 있는 채널/브랜드 메시지
- 상세 UI/대시보드: Post-MVP 또는 내부 운영 도구

## 운영 백오피스: Ops Admin Web

`ops-admin/` 은 **Next.js 16 LTS(App Router · React 19 · Turbopack) + Tailwind v4 + shadcn/ui + TanStack Query + next-intl** 기반의 독립 웹 백오피스다. 조달 수집 주문, 최저 실가 결과, 카카오/SMS 알림 수신자 현황, 내부 파서 실험 데이터를 운영자가 확인하는 용도로 사용한다.

```bash
make install-ui
make dev-ui          # http://127.0.0.1:5175
make typecheck-ui
make test-ui         # Vitest + RTL (13 tests)
make test-ui-e2e     # Playwright smoke (6 tests)
make build-ui
```

`/settings` 페이지에서 백엔드 URL과 Bearer 토큰을 입력하면 TanStack Query 훅이 실데이터 모드로 즉시 전환한다. 토큰 미설정 상태에서는 각 페이지가 NotConnectedState 로 설정 페이지 이동을 안내하며, 대시보드/주문/결과/알림/실험/설정 라우트가 준비되어 있다. 사용자-facing 결과 전달은 여전히 `pivot-noti-first-procurement`의 notification workflow가 담당한다.

주요 기술 스택:

- Next.js 16.2 (App Router, Server Components, Turbopack dev)
- React 19 · TypeScript 5 strict(noUncheckedIndexedAccess) · ESLint(next/core-web-vitals) · Prettier
- Tailwind CSS v4 (CSS-first `@theme` · OKLCH 팔레트) · shadcn/ui new-york · lucide-react
- TanStack Query v5(+devtools), Zod v4 스키마 검증, sonner 토스트
- next-intl 4 (cookie 기반 ko/en 전환, server action), next-themes (시스템/라이트/다크)
- Recharts 3 (대시보드 차트), date-fns 4
- Vitest 3 + @testing-library, Playwright 1.59 E2E

## 주요 엔드포인트

### 인증 (비인증)

- `GET /api/v1/auth/{provider}/login` — 카카오·네이버 OAuth 진입점 (state CSRF Redis 저장)
- `GET /api/v1/auth/{provider}/callback` — 프로바이더 콜백, `TokenPair` 반환
- `POST /api/v1/auth/refresh` — refresh 회전 (기존 jti revoke)
- `POST /api/v1/auth/logout` — 현재 refresh jti revoke

### 테넌트/매장 (Bearer JWT 필요)

- `GET /api/v1/tenants/me` — 현재 사용자의 테넌트
- `POST /api/v1/shops`, `GET /api/v1/shops`, `GET /api/v1/shops/{id}` — 매장 관리 (테넌트 격리)
- `GET /api/v1/users/me` — 내 계정

### 조달 (Bearer JWT 필요)

- `POST /api/v1/procurement/orders`, `GET /api/v1/procurement/orders`, `GET /api/v1/procurement/orders/{id}`
- `POST /api/v1/procurement/orders/{id}/results` — 결과 업로드 (쿼터 소비)
- `GET /api/v1/procurement/orders/{id}/results` — per_unit_price ASC
- `POST /api/v1/procurement/orders/{id}/collect` — 네이버 공식 쇼핑 검색 기반 최저가 수집 job 생성 (멱등 키 지원)
- `GET /api/v1/procurement/orders/{id}/collect/jobs` — 수집 job 목록 조회
- `GET /api/v1/procurement/reports/summary?from=&to=` — 기간별 절감액 집계

### 검색 (Bearer JWT 필요)

- `GET /api/v1/search` — 업로드된 `procurement_results` 기반 테넌트 스코프 랭킹. 캐시 네임스페이스 `search:{tenant_id}:...`, 쿼터 소비 포함.

### 헬스 체크

- `GET /health/live`, `GET /health/ready`

## 필수 환경변수

`.env.example` 참조. 최소 `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET` 은 지정해야 기동한다. OAuth 로그인을 쓰려면 `KAKAO_CLIENT_ID`, `NAVER_OAUTH_CLIENT_ID` 등 OAuth 시크릿 값도 함께 설정한다.

최저가 수집을 사용하려면 다음 값도 필요하다.

- `NAVER_SEARCH_CLIENT_ID`
- `NAVER_SEARCH_CLIENT_SECRET`
- `NAVER_SEARCH_DISPLAY_LIMIT` (기본 20)
- `PRICE_COLLECTION_MAX_ATTEMPTS` (기본 3)
- `PRICE_COLLECTION_RETRY_BASE_SECONDS` (기본 60)

## 문서

- [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) — 조사 결과와 핵심 제약
- [openspec/changes/pivot-backend-multi-tenant/](./openspec/changes/pivot-backend-multi-tenant/) — B2B 멀티테넌트 피벗 스펙 (proposal / design / specs / tasks)
- [openspec/changes/pivot-noti-first-procurement/](./openspec/changes/pivot-noti-first-procurement/) — Noti-first 조달 결과 알림 피벗 스펙 (proposal / design / specs / tasks)

## 테스트

```bash
make test
```

- 신규 모듈(tenancy / auth / procurement / services) 테스트 포함 총 **135개 통과**
- 주요 모듈 커버리지 (`pytest --cov`):
  - `app.tenancy` models 100% / service 98%
  - `app.auth` service 92% / jwt 92%
  - `app.procurement` router 94% / service 90%
  - `app.services.search_service` 92%, `quota_service` 94%
- 테스트 격리: SQLite in-memory + fakeredis + respx (외부 OAuth stub)

## 라이선스

비공개 개인 프로젝트 — 외부 배포 및 재사용 금지.
