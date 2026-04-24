# lowest-price Tauri Internal Tooling

React + TypeScript + Vite 기반의 내부 파서 QA·운영자 디버깅·optional ingestion 실험 도구입니다.

> 사용자-facing 제품 방향은 `openspec/changes/pivot-noti-first-procurement/`의 Noti-first 조달 결과 알림 서비스가 기준입니다. 이 Tauri 앱은 더 이상 1차 제품 UI/UX가 아닙니다.

## 개발

```bash
pnpm install
pnpm dev
```

## 검증

```bash
pnpm typecheck
pnpm test -- --run
pnpm build
```

## Tauri 실행 준비

Rust/Tauri 의존성이 준비된 환경에서:

```bash
pnpm tauri dev
```

현재 Rust 명령은 쿠팡/네이버 검색 페이지를 직접 조회·파싱하는 로컬 검색 경로를 포함합니다. 이 경로는 사용자 배포용이 아니라 parser QA와 ingestion 실험용입니다.

## 실제 검색 경로

`search_marketplace_items` Tauri command가 품목별 쿠팡/네이버 검색 페이지를 조회한 뒤 후보 상세 페이지를 보강하고, 가격·배송비·수량 힌트를 파싱합니다. API 설정이 연결되어 있으면 결과를 `/api/v1/procurement/orders/{id}/results`로 업로드할 수 있으며, 사용자-facing 전달은 알림 워크플로가 담당합니다.
