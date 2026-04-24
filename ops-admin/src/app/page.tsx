import Link from "next/link";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-2xl flex-col justify-center gap-6 px-6 py-16">
      <div className="flex items-center gap-3">
        <div className="flex size-10 items-center justify-center rounded-md bg-primary font-semibold text-primary-foreground">
          O
        </div>
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Ops Console</h1>
          <p className="text-sm text-muted-foreground">Lowest Price · internal admin</p>
        </div>
      </div>

      <div className="rounded-lg border bg-card p-6 shadow-xs">
        <h2 className="text-sm font-medium text-card-foreground">Next.js 16 스캐폴드 완료</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Tailwind v4 · shadcn/ui · TypeScript strict · App Router 기반의 운영 백오피스
          베이스 구성을 마쳤습니다. 후속 커밋에서 사이드바 레이아웃, API 연동, 주요 뷰를
          점진적으로 추가합니다.
        </p>
        <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
          <div className="rounded-md border bg-muted/40 px-3 py-2">
            <dt className="text-muted-foreground">Node</dt>
            <dd className="mt-0.5 font-medium">22 LTS (Jod)</dd>
          </div>
          <div className="rounded-md border bg-muted/40 px-3 py-2">
            <dt className="text-muted-foreground">Next.js</dt>
            <dd className="mt-0.5 font-medium">16.2 LTS</dd>
          </div>
          <div className="rounded-md border bg-muted/40 px-3 py-2">
            <dt className="text-muted-foreground">Tailwind</dt>
            <dd className="mt-0.5 font-medium">v4 (CSS-first)</dd>
          </div>
          <div className="rounded-md border bg-muted/40 px-3 py-2">
            <dt className="text-muted-foreground">UI Kit</dt>
            <dd className="mt-0.5 font-medium">shadcn/ui · new-york</dd>
          </div>
        </dl>
      </div>

      <nav className="flex flex-wrap gap-2 text-sm">
        <Link
          className="rounded-md border px-3 py-1.5 text-muted-foreground transition hover:bg-accent hover:text-accent-foreground"
          href="/"
        >
          홈
        </Link>
        <span className="rounded-md border px-3 py-1.5 text-muted-foreground/60">
          Jobs · 다음 커밋
        </span>
        <span className="rounded-md border px-3 py-1.5 text-muted-foreground/60">
          Results · 다음 커밋
        </span>
        <span className="rounded-md border px-3 py-1.5 text-muted-foreground/60">
          Notifications · 다음 커밋
        </span>
      </nav>
    </main>
  );
}
