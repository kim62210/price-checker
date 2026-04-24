"use client";

import { useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState } from "@/components/shared/empty-state";
import { NotConnectedState } from "@/components/shared/not-connected";
import { OrderStatusBadge } from "@/components/shared/status-badge";
import { useApiConfig } from "@/lib/api/config";
import {
  useOrdersQuery,
  useTriggerCollectMutation,
} from "@/lib/api/queries";
import { formatInteger, formatRelativeTime } from "@/lib/format";
import type { OrderRead } from "@/types/api";
import { OrderDetailSheet } from "./order-detail-sheet";

type TabValue = "all" | "draft" | "collecting" | "completed" | "cancelled";

const TABS: TabValue[] = ["all", "draft", "collecting", "completed", "cancelled"];

function filterByTab(orders: OrderRead[], tab: TabValue): OrderRead[] {
  if (tab === "all") return orders;
  return orders.filter((order) => order.status === tab);
}

function filterByQuery(orders: OrderRead[], query: string): OrderRead[] {
  if (!query.trim()) return orders;
  const needle = query.trim().toLowerCase();
  return orders.filter((order) => {
    return (
      order.product_name.toLowerCase().includes(needle) ||
      (order.option_text?.toLowerCase().includes(needle) ?? false) ||
      String(order.id).includes(needle) ||
      (order.memo?.toLowerCase().includes(needle) ?? false)
    );
  });
}

export function JobsView() {
  const jobs = useTranslations("jobs");
  const common = useTranslations("common");
  const locale = useLocale();
  const { isAuthorized, isHydrated } = useApiConfig();
  const [tab, setTab] = useState<TabValue>("all");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const ordersQuery = useOrdersQuery();
  const triggerCollect = useTriggerCollectMutation();

  const filtered = useMemo(() => {
    if (!ordersQuery.data) return [];
    return filterByQuery(filterByTab(ordersQuery.data, tab), query);
  }, [ordersQuery.data, tab, query]);

  const totals = useMemo(() => {
    const base = ordersQuery.data ?? [];
    return {
      all: base.length,
      draft: base.filter((o) => o.status === "draft").length,
      collecting: base.filter((o) => o.status === "collecting").length,
      completed: base.filter((o) => o.status === "completed").length,
      cancelled: base.filter((o) => o.status === "cancelled").length,
    } satisfies Record<TabValue, number>;
  }, [ordersQuery.data]);

  if (!isHydrated) {
    return <Skeleton className="h-[200px] w-full" />;
  }

  if (!isAuthorized) {
    return <NotConnectedState />;
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <Tabs value={tab} onValueChange={(value) => setTab(value as TabValue)}>
          <TabsList>
            {TABS.map((value) => (
              <TabsTrigger key={value} value={value} className="capitalize">
                {jobs(`tabs.${value}`)}
                <Badge
                  variant="outline"
                  className="ml-2 h-4 min-w-4 rounded-full px-1 font-mono text-[10px]"
                >
                  {formatInteger(locale, totals[value])}
                </Badge>
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        <Input
          type="search"
          placeholder={jobs("search")}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="h-8 w-full text-xs md:w-64"
          aria-label={jobs("search")}
        />
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-24">{jobs("table.job")}</TableHead>
              <TableHead>{jobs("table.order")}</TableHead>
              <TableHead className="w-28">{jobs("table.status")}</TableHead>
              <TableHead className="w-20 text-right">{jobs("table.quantity")}</TableHead>
              <TableHead className="w-36">{jobs("table.queued")}</TableHead>
              <TableHead className="w-20 text-right">{jobs("table.actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {ordersQuery.isLoading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <TableRow key={`loading-${i}`}>
                  {Array.from({ length: 6 }).map((__, j) => (
                    <TableCell key={`loading-cell-${j}`}>
                      <Skeleton className="h-4 w-full" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="h-32 text-center">
                  <div className="mx-auto max-w-sm text-xs text-muted-foreground">
                    {common("empty")}
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              filtered.map((order) => (
                <TableRow
                  key={order.id}
                  data-state={selectedId === order.id ? "selected" : undefined}
                  className="cursor-pointer"
                  onClick={() => setSelectedId(order.id)}
                >
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    order#{order.id}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col gap-0.5">
                      <span className="text-sm font-medium">{order.product_name}</span>
                      {order.option_text ? (
                        <span className="text-xs text-muted-foreground">
                          {order.option_text}
                        </span>
                      ) : null}
                    </div>
                  </TableCell>
                  <TableCell>
                    <OrderStatusBadge status={order.status} />
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs tabular-nums">
                    {formatInteger(locale, order.quantity)}
                    <span className="ml-0.5 text-muted-foreground">{order.unit}</span>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {formatRelativeTime(locale, order.created_at)}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      size="icon-sm"
                      variant="ghost"
                      title={jobs("actions.triggerCollect")}
                      disabled={
                        order.status === "cancelled" ||
                        (triggerCollect.isPending && triggerCollect.variables === order.id)
                      }
                      onClick={(event) => {
                        event.stopPropagation();
                        triggerCollect.mutate(order.id, {
                          onSuccess: () => toast.success(jobs("actions.triggered")),
                        });
                      }}
                    >
                      {triggerCollect.isPending && triggerCollect.variables === order.id ? (
                        <Loader2 className="size-3 animate-spin" />
                      ) : (
                        <RefreshCw className="size-3" />
                      )}
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {ordersQuery.isError ? (
        <EmptyState
          title={common("error")}
          description={String(ordersQuery.error?.message ?? common("empty"))}
        />
      ) : null}

      <OrderDetailSheet
        orderId={selectedId}
        open={selectedId !== null}
        onOpenChange={(open) => {
          if (!open) setSelectedId(null);
        }}
      />
    </div>
  );
}
