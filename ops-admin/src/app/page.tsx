import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { navGroups } from "@/lib/nav";

export default function DashboardHome() {
  const allItems = navGroups.flatMap((group) => group.items).filter((item) => item.href !== "/");

  return (
    <div className="flex flex-1 flex-col gap-6 p-4 md:gap-8 md:p-6">
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-semibold tracking-tight">대시보드</h1>
          <Badge variant="outline" className="font-mono text-[10px]">
            STG
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">
          수집 · 절감 · 알림 지표와 최근 이벤트를 한 화면에 모아 확인합니다.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "실행 중 수집", value: "—", hint: "API 연결 대기" },
          { label: "24h 절감액", value: "—", hint: "API 연결 대기" },
          { label: "알림톡 전달률", value: "—", hint: "API 연결 대기" },
          { label: "활성 수신자", value: "—", hint: "API 연결 대기" },
        ].map((kpi) => (
          <Card key={kpi.label}>
            <CardHeader className="pb-2">
              <CardDescription>{kpi.label}</CardDescription>
              <CardTitle className="text-2xl font-semibold tabular-nums">{kpi.value}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">{kpi.hint}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div>
        <h2 className="mb-3 text-sm font-medium text-muted-foreground">빠른 이동</h2>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {allItems.map((item) => {
            const Icon = item.icon;
            return (
              <Card key={item.href} className="transition-all hover:border-ring/50 hover:shadow-xs">
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Icon className="size-4 text-muted-foreground" />
                    <CardTitle className="text-sm">{item.title}</CardTitle>
                  </div>
                  <CardDescription className="text-xs">{item.description}</CardDescription>
                </CardHeader>
                <CardFooter className="pt-0">
                  <Link
                    href={item.href}
                    className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                  >
                    바로가기 <ArrowRight className="size-3" />
                  </Link>
                </CardFooter>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}
