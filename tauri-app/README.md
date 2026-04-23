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

현재 네이티브 WebView 자동화는 후속 구현 범위이며, Rust 명령은 UI 연동용 placeholder 입니다.
