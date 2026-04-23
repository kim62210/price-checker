# lowest-price

B2B 조달 SaaS 백엔드 (**멀티테넌트 피벗 완료**).

테넌트별 발주 이력과 업로드된 상품 옵션 데이터를 기반으로 "배송비 포함 개당 실가" 오름차순 비교·리포트를 제공한다.

> **피벗 완료**: `openspec/changes/pivot-backend-multi-tenant/` 변경 스펙의 Wave 1~4 구현이 모두 반영됐다. 크롤링 기반 MVP 에서 JWT + 카카오/네이버 OAuth 인증·멀티테넌트·조달 업로드·테넌트 스코프 검색 구조로 전환됐다.

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
- `GET /api/v1/procurement/reports/summary?from=&to=` — 기간별 절감액 집계

### 검색 (Bearer JWT 필요)

- `GET /api/v1/search` — 업로드된 `procurement_results` 기반 테넌트 스코프 랭킹. 캐시 네임스페이스 `search:{tenant_id}:...`, 쿼터 소비 포함.

### 헬스 체크

- `GET /health/live`, `GET /health/ready`

## 필수 환경변수

`.env.example` 참조. 최소 `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET` 은 지정해야 기동한다. OAuth 로그인을 쓰려면 `KAKAO_CLIENT_ID`, `NAVER_OAUTH_CLIENT_ID` 등 OAuth 시크릿 값도 함께 설정한다.

## 문서

- [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) — 조사 결과와 핵심 제약
- [openspec/changes/pivot-backend-multi-tenant/](./openspec/changes/pivot-backend-multi-tenant/) — B2B 멀티테넌트 피벗 스펙 (proposal / design / specs / tasks)

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
