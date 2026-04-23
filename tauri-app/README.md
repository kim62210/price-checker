# lowest-price Tauri UI

React + TypeScript + Vite 기반의 lowest-price 데스크톱 UI/UX 스켈레톤입니다.

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

현재 Rust 명령은 쿠팡/네이버 검색 페이지를 사장님 PC에서 직접 조회·파싱하는 로컬 검색 경로를 포함합니다. foreground WebView 로그인 창과 상세 페이지 옵션 파싱 고도화는 후속 범위입니다.

## 실제 검색 경로

`search_marketplace_items` Tauri command가 품목별 쿠팡/네이버 검색 페이지를 조회한 뒤 후보 상세 페이지를 보강하고, 가격·배송비·수량 힌트를 파싱해 React 비교표에 전달합니다. API 설정이 연결되어 있으면 결과를 `/api/v1/procurement/orders/{id}/results`로 업로드합니다.
