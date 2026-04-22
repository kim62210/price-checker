# lowest-price

친구 몇 명이 쓰는 **네이버 스마트스토어 / 쿠팡 최저가 비교 도구**.
상품 검색어 하나로 양쪽 플랫폼의 후보 상품을 모두 수집하고, 옵션 텍스트에서 실 수량을 역파싱해 **"배송비 포함 개당 실가"** 오름차순으로 정렬해 보여준다.

> **비공개 친구용 도구** — 외부 공개·상용화 용도 아님. 실 사용 시 각 플랫폼 이용약관을 존중해 저빈도로만 호출한다.

---

## 빠른 시작

```bash
cp .env.example .env
# NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 채우기

make install
make install-playwright
make migrate
make dev             # Docker Compose 로 전체 스택 기동
# 또는
make dev-api         # API 만
make dev-ui          # Streamlit UI 만
```

- API 기본 주소: `http://localhost:8000`
- UI 기본 주소: `http://localhost:8501`
- 헬스 체크: `curl http://localhost:8000/health/live`

## 주요 엔드포인트

- `GET /api/v1/search?q=<keyword>&limit=<n>` — 네이버·쿠팡 병렬 수집 + 개당 실가 정렬 결과
- `GET /health/live`, `GET /health/ready`

## 필수 환경변수

`.env.example` 참조. 최소 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `DATABASE_URL`, `REDIS_URL` 은 지정해야 기동한다.

## 문서

- [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) — 조사 결과와 핵심 제약
- [openspec/changes/add-lowest-price-mvp/](./openspec/changes/add-lowest-price-mvp/) — MVP 변경 스펙 (proposal / design / specs / tasks)

## 테스트

```bash
make test
```

- 정규식 파서 파라미터라이즈 케이스, 개당 실가 계산, 랭킹, 배송비 정책, 캐시 키, 토큰 버킷 등 핵심 모듈 단위 테스트 포함.
- 커버리지 80% 이상을 목표로 하지만, 초기 구현에서는 수집기/상세 페이지 실망 네트워크 의존성 테스트는 VCR/respx 추가가 필요하다(후속 작업).

## 교차검증이 필요한 항목

운영 전 다음을 공식 문서에서 직접 재확인한다.

- 네이버 쇼핑 API `productType` 숫자 코드 매핑
- 네이버 검색 API 이용 시 로고·출처 표기 의무
- 쿠팡 상세 페이지 접근 차단 빈도 (실측)
- LLM 폴백 월 토큰 한도 설정 적정성

## 라이선스

비공개 개인 프로젝트 — 외부 배포 및 재사용 금지.
