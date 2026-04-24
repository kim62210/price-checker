# ops-admin

Lowest Price 운영 백오피스 (Next.js 16 LTS · App Router).

## 요구 환경

- Node.js **22 LTS (Jod)** — `.nvmrc` 참고
- pnpm 9.x

## 로컬 실행

```bash
pnpm install
pnpm dev             # http://127.0.0.1:5175
pnpm typecheck
pnpm test            # Vitest + RTL
pnpm test:coverage   # v8 커버리지 리포트
pnpm test:e2e        # Playwright 스모크 (dev 서버 자동 기동)
pnpm build
pnpm start           # 프로덕션 서버
```

루트에서는 Makefile 타겟으로 동일하게 제어한다.

```bash
make install-ui
make dev-ui
make typecheck-ui
make test-ui
make test-ui-e2e
make build-ui
```

## 주요 환경 변수

| 변수                          | 설명                                                                                          | 기본값                    |
| ----------------------------- | --------------------------------------------------------------------------------------------- | ------------------------- |
| `NEXT_PUBLIC_BACKEND_URL`     | 런타임 백엔드 기본 URL (localStorage 설정이 없을 때 fallback). 각 브라우저 설정 페이지에서 덮어쓸 수 있다. | `http://localhost:8000`  |

- Bearer 토큰은 `/settings` 페이지에서 브라우저 localStorage(`lowest-price.ops-admin.api-config`)에 저장된다.
- 로케일은 쿠키 `lowest-price.locale` 로 관리된다 (`ko` 기본, `en` 지원).

## 스택

- Next.js 16.2 (App Router · React 19 · Turbopack · typedRoutes)
- Tailwind CSS v4 (CSS-first `@theme`, OKLCH 팔레트)
- shadcn/ui (new-york · zinc · data-slot, sidebar/sheet/dialog/table/chart 등)
- TypeScript 5 strict(`noUncheckedIndexedAccess`) · ESLint(next/core-web-vitals) · Prettier(tailwindcss 플러그인)
- TanStack Query v5 (+devtools) · Zod v4 스키마 검증 · sonner 토스트 · react-hook-form + @hookform/resolvers
- next-intl 4 (cookie 기반 ko/en 전환, Server Action) · next-themes (시스템/라이트/다크)
- Recharts 3 · date-fns 4
- Vitest 3 + @testing-library · Playwright 1.59 (chromium)

## 구조

```
src/
├── app/                  # App Router (layout, page, route groups)
│   ├── layout.tsx        # NextIntlClientProvider + Providers + AppShell
│   ├── page.tsx          # 대시보드
│   ├── jobs/page.tsx
│   ├── results/page.tsx
│   ├── notifications/page.tsx
│   ├── experiments/page.tsx
│   └── settings/page.tsx
├── components/
│   ├── ui/               # shadcn/ui 프리미티브
│   ├── shared/           # EmptyState, PageHeader, StatusBadge, NotConnected 등
│   ├── dashboard/        # KpiCard, DashboardView
│   ├── jobs/             # JobsView, OrderDetailSheet
│   ├── results/          # ResultsView
│   ├── notifications/    # NotificationsView
│   ├── experiments/      # ExperimentsView (탭 골격)
│   ├── settings/         # ApiConfigCard, PreferencesCard
│   ├── app-shell.tsx     # SidebarProvider + SiteHeader wrapper
│   ├── app-sidebar.tsx   # 운영·내부 네비게이션
│   ├── site-header.tsx   # 브레드크럼 · 검색 · 토글
│   ├── providers.tsx     # Theme + Query + ApiConfig + Tooltip + Sonner
│   ├── theme-toggle.tsx
│   ├── locale-toggle.tsx
│   └── connection-badge.tsx
├── lib/
│   ├── api/              # client, endpoints, schemas, procurement, notifications, queries, query-provider, config
│   ├── format.ts         # Intl 기반 통화/정수/퍼센트/상대시간 포매터
│   ├── nav.ts            # 사이드바 NavItem 정의
│   └── utils.ts          # cn 헬퍼
├── i18n/
│   ├── config.ts         # locales, 쿠키 키
│   ├── request.ts        # getRequestConfig (쿠키 → locale → messages)
│   └── actions.ts        # setLocaleAction (Server Action)
├── hooks/
│   └── use-mobile.ts
├── types/
│   └── api.ts            # 백엔드 계약 타입
└── test-setup.ts         # Vitest + RTL cleanup

messages/                 # next-intl 번역 메시지 (ko.json, en.json)
tests/e2e/                # Playwright 스모크 (smoke.spec.ts)
```
