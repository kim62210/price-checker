"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { Activity, ArrowRight, BellRing, Package, TrendingUp } from "lucide-react";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ChartConfig,
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import { KpiCard } from "@/components/dashboard/kpi-card";
import {
  useNotificationRecipientsQuery,
  useOrdersQuery,
  useSummaryQuery,
} from "@/lib/api/queries";
import { useApiConfig } from "@/lib/api/config";
import { formatCompactNumber, formatCurrencyKRW, formatInteger, toNumber } from "@/lib/format";
import type { OrderRead } from "@/types/api";
import { navGroups } from "@/lib/nav";

const ORDER_STATUS_ORDER: OrderRead["status"][] = [
  "draft",
  "collecting",
  "completed",
  "cancelled",
];

const chartConfig = {
  count: {
    label: "주문",
    color: "var(--chart-1)",
  },
} satisfies ChartConfig;

function countByStatus(orders: OrderRead[]): Record<OrderRead["status"], number> {
  const acc: Record<OrderRead["status"], number> = {
    draft: 0,
    collecting: 0,
    completed: 0,
    cancelled: 0,
  };
  for (const order of orders) {
    acc[order.status] = (acc[order.status] ?? 0) + 1;
  }
  return acc;
}

export function DashboardView() {
  const dashboard = useTranslations("dashboard");
  const nav = useTranslations("nav");
  const common = useTranslations("common");
  const locale = useLocale();
  const { isAuthorized } = useApiConfig();

  const ordersQuery = useOrdersQuery();
  const summaryQuery = useSummaryQuery();
  const recipientsQuery = useNotificationRecipientsQuery();

  const statusDistribution = useMemo(() => {
    if (!ordersQuery.data) return null;
    const counts = countByStatus(ordersQuery.data);
    return ORDER_STATUS_ORDER.map((status) => ({ status, count: counts[status] }));
  }, [ordersQuery.data]);

  const activeJobs = ordersQuery.data?.filter((order) => order.status === "collecting").length;
  const completedOrders = summaryQuery.data?.completed_orders_count;
  const totalSavings = summaryQuery.data ? toNumber(summaryQuery.data.total_savings) : undefined;
  const activeRecipients = recipientsQuery.data?.filter((r) => r.is_active).length;

  const hasOrders = (ordersQuery.data?.length ?? 0) > 0;
  const recentOrders = ordersQuery.data?.slice(0, 5) ?? [];
  const quickLinks = navGroups
    .flatMap((group) => group.items)
    .filter((item) => item.href !== "/" && item.href !== "/settings");

  return (
    <div className="flex flex-1 flex-col gap-6 p-4 md:gap-8 md:p-6">
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-semibold tracking-tight">{dashboard("title")}</h1>
        </div>
        <p className="text-sm text-muted-foreground">{dashboard("description")}</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label={dashboard("kpi.activeJobs")}
          icon={Activity}
          value={
            isAuthorized && activeJobs !== undefined
              ? formatInteger(locale, activeJobs)
              : "—"
          }
          helper={isAuthorized ? undefined : dashboard("kpi.apiPending")}
          isLoading={isAuthorized && ordersQuery.isLoading}
        />
        <KpiCard
          label={dashboard("kpi.savings24h")}
          icon={TrendingUp}
          value={
            isAuthorized && totalSavings !== undefined
              ? formatCurrencyKRW(locale, totalSavings)
              : "—"
          }
          helper={
            isAuthorized && completedOrders !== undefined
              ? `${formatInteger(locale, completedOrders)} orders`
              : dashboard("kpi.apiPending")
          }
          isLoading={isAuthorized && summaryQuery.isLoading}
        />
        <KpiCard
          label={dashboard("kpi.alimtalkRate")}
          icon={BellRing}
          value="—"
          helper={dashboard("kpi.apiPending")}
        />
        <KpiCard
          label={dashboard("kpi.activeRecipients")}
          icon={Package}
          value={
            isAuthorized && activeRecipients !== undefined
              ? formatInteger(locale, activeRecipients)
              : "—"
          }
          helper={
            isAuthorized && recipientsQuery.data
              ? `${formatCompactNumber(locale, recipientsQuery.data.length)} registered`
              : dashboard("kpi.apiPending")
          }
          isLoading={isAuthorized && recipientsQuery.isLoading}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-sm">조달 주문 상태 분포</CardTitle>
            <CardDescription className="text-xs">
              전체 주문 대비 draft · collecting · completed · cancelled 분포.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isAuthorized && statusDistribution ? (
              <ChartContainer config={chartConfig} className="h-[240px] w-full">
                <BarChart data={statusDistribution} accessibilityLayer>
                  <CartesianGrid vertical={false} strokeDasharray="4 4" />
                  <XAxis
                    dataKey="status"
                    tickLine={false}
                    axisLine={false}
                    tickMargin={8}
                    className="text-xs"
                  />
                  <YAxis
                    allowDecimals={false}
                    tickLine={false}
                    axisLine={false}
                    width={28}
                    className="text-xs"
                  />
                  <ChartTooltip content={<ChartTooltipContent indicator="dashed" />} />
                  <ChartLegend content={<ChartLegendContent />} />
                  <Bar dataKey="count" fill="var(--color-count)" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ChartContainer>
            ) : (
              <div className="flex h-[240px] flex-col items-center justify-center gap-2 rounded-md border border-dashed text-xs text-muted-foreground">
                <span>{dashboard("kpi.apiPending")}</span>
                <Link
                  href="/settings"
                  className="inline-flex items-center gap-1 text-primary hover:underline"
                >
                  <ArrowRight className="size-3" />
                  {nav("items.settings.title")}
                </Link>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">최근 조달 주문</CardTitle>
            <CardDescription className="text-xs">
              최신 5건의 조달 주문 요약.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isAuthorized && hasOrders ? (
              <ul className="flex flex-col divide-y">
                {recentOrders.map((order) => (
                  <li key={order.id} className="flex items-center justify-between gap-3 py-2">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium">{order.product_name}</div>
                      <div className="text-xs text-muted-foreground">
                        order#{order.id} · qty {order.quantity}
                      </div>
                    </div>
                    <Badge variant="outline" className="font-mono text-[10px] capitalize">
                      {order.status}
                    </Badge>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="flex h-full min-h-[160px] flex-col items-center justify-center gap-1 text-xs text-muted-foreground">
                <span>{common("empty")}</span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div>
        <h2 className="mb-3 text-sm font-medium text-muted-foreground">
          {dashboard("quickLinks")}
        </h2>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          {quickLinks.map((item) => {
            const Icon = item.icon;
            return (
              <Card
                key={item.href}
                className="transition-all hover:border-ring/50 hover:shadow-xs"
              >
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2">
                    <Icon className="size-4 text-muted-foreground" />
                    <CardTitle className="text-sm">
                      {nav(`items.${item.key}.title`)}
                    </CardTitle>
                  </div>
                  <CardDescription className="text-xs">
                    {nav(`items.${item.key}.description`)}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Button variant="ghost" size="sm" asChild className="-ml-2">
                    <Link href={item.href}>
                      {dashboard("goTo")} <ArrowRight className="size-3" />
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}

