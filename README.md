# lowest-price

B2B 조달 SaaS 백엔드 (**멀티테넌트 피벗 진행 중**).

테넌트별 발주 이력과 업로드된 상품 옵션 데이터를 기반으로 "배송비 포함 개당 실가" 오름차순 비교·리포트를 제공한다.

> **피벗 상태**: `openspec/changes/pivot-backend-multi-tenant/` 변경 스펙에 따라 크롤링 기반 MVP 에서 인증·멀티테넌트·조달 업로드 구조로 전환 중. Wave 3 에서 `search_service`, `quota_service`, `cache_service`, `option_parser` 가 테넌트 스코프로 재설계된다.

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

## 주요 엔드포인트 (Wave 1 기준)

- `GET /api/v1/auth/{provider}/login` — 카카오·네이버 OAuth 진입점
- `GET /api/v1/auth/{provider}/callback`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`
- `/api/v1/tenants/me`, `/api/v1/shops`, `/api/v1/users`
- `POST /api/v1/orders`, `GET /api/v1/orders`, `POST /api/v1/orders/{id}/results` 등 조달 오더
- `GET /health/live`, `GET /health/ready`

> `GET /api/v1/search` 는 Wave 3 재설계 완료 전까지 비활성 상태.

## 필수 환경변수

`.env.example` 참조. 최소 `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET` 은 지정해야 기동한다. OAuth 로그인을 쓰려면 `KAKAO_CLIENT_ID`, `NAVER_OAUTH_CLIENT_ID` 등 OAuth 시크릿 값도 함께 설정한다.

## 문서

- [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) — 조사 결과와 핵심 제약
- [openspec/changes/pivot-backend-multi-tenant/](./openspec/changes/pivot-backend-multi-tenant/) — B2B 멀티테넌트 피벗 스펙 (proposal / design / specs / tasks)

## 테스트

```bash
make test
```

- 정규식 파서, 개당 실가 계산, 랭킹, 배송비 정책, 캐시 키 등 재사용 가능한 모듈 단위 테스트 유지
- Wave 4 에서 tenancy / auth / procurement 신규 모듈 테스트 및 커버리지 80% 목표 달성 예정

## 라이선스

비공개 개인 프로젝트 — 외부 배포 및 재사용 금지.
