# ops-admin

Lowest Price 운영 백오피스 (Next.js 16 LTS · App Router).

## 요구 환경

- Node.js **22 LTS (Jod)** — `.nvmrc` 참고
- pnpm 9.x

## 로컬 실행

```bash
pnpm install
pnpm dev         # http://127.0.0.1:5175
pnpm typecheck
pnpm test
pnpm build
```

루트에서는 기존 Makefile 타겟을 그대로 사용할 수 있다.

```bash
make install-ui
make dev-ui
make typecheck-ui
make test-ui
make build-ui
```

## 스택

- Next.js 16.2 (App Router, React 19, Turbopack)
- Tailwind CSS v4 (CSS-first `@theme`)
- shadcn/ui (new-york, zinc base, data-slot)
- TypeScript 5 strict · ESLint (next/core-web-vitals) · Prettier
- Vitest (단위/컴포넌트) · Playwright (E2E 스모크)

## 구조

```
src/
├── app/           # App Router (layout, page, route groups)
├── components/
│   └── ui/        # shadcn/ui 프리미티브
├── lib/           # utils, api client, query helpers
├── hooks/
└── types/
```
