"use client";

import { useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { ExternalLink } from "lucide-react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/shared/empty-state";
import { NotConnectedState } from "@/components/shared/not-connected";
import { SourceBadge } from "@/components/shared/status-badge";
import { useApiConfig } from "@/lib/api/config";
import {
  useMultiOrderResultsQuery,
  useOrdersQuery,
} from "@/lib/api/queries";
import { formatCurrencyKRW, formatDateTime, formatInteger, toNumber } from "@/lib/format";
import type { OrderRead, ResultRead, ResultSource } from "@/types/api";

type SourceTab = "all" | ResultSource;

const SOURCE_TABS: SourceTab[] = ["all", "naver", "coupang", "manual"];
const TOP_N_ORDERS = 20;

interface EnrichedResult extends ResultRead {
  order?: OrderRead;
  rank?: number;
}

export function ResultsView() {
  const results = useTranslations("results");
  const common = useTranslations("common");
  const locale = useLocale();
  const { isAuthorized, isHydrated } = useApiConfig();

  const ordersQuery = useOrdersQuery();
  const orderIds = useMemo(
    () => ordersQuery.data?.slice(0, TOP_N_ORDERS).map((order) => order.id) ?? [],
    [ordersQuery.data],
  );
  const resultsQueries = useMultiOrderResultsQuery(orderIds);

  const [sourceTab, setSourceTab] = useState<SourceTab>("all");
  const [selectedOrderId, setSelectedOrderId] = useState<"all" | number>("all");

  const allResults = useMemo<EnrichedResult[]>(() => {
    const orders = ordersQuery.data ?? [];
    const enriched: EnrichedResult[] = [];
    resultsQueries.forEach((query, index) => {
      const order = orders[index];
      const list = query.data ?? [];
      list.forEach((result, rank) => {
        enriched.push({ ...result, order, rank: rank + 1 });
      });
    });
    return enriched;
  }, [ordersQuery.data, resultsQueries]);

  const filtered = useMemo(() => {
    return allResults
      .filter((result) => {
        if (sourceTab !== "all" && result.source !== sourceTab) return false;
        if (selectedOrderId !== "all" && result.order_id !== selectedOrderId) return false;
        return true;
      })
      .sort((a, b) => toNumber(a.per_unit_price) - toNumber(b.per_unit_price));
  }, [allResults, sourceTab, selectedOrderId]);

  const tabCounts = useMemo(() => {
    const acc: Record<SourceTab, number> = { all: 0, naver: 0, coupang: 0, manual: 0 };
    allResults.forEach((result) => {
      if (selectedOrderId !== "all" && result.order_id !== selectedOrderId) return;
      acc.all += 1;
      acc[result.source] += 1;
    });
    return acc;
  }, [allResults, selectedOrderId]);

  if (!isHydrated) {
    return <Skeleton className="h-[200px] w-full" />;
  }
  if (!isAuthorized) {
    return <NotConnectedState />;
  }
  if (ordersQuery.isLoading) {
    return <Skeleton className="h-[200px] w-full" />;
  }

  const isLoadingResults = resultsQueries.some((query) => query.isLoading);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <Tabs value={sourceTab} onValueChange={(value) => setSourceTab(value as SourceTab)}>
          <TabsList>
            {SOURCE_TABS.map((value) => (
              <TabsTrigger key={value} value={value} className="capitalize">
                {value === "all" ? results("tabs.all") : value}
                <Badge
                  variant="outline"
                  className="ml-2 h-4 min-w-4 rounded-full px-1 font-mono text-[10px]"
                >
                  {formatInteger(locale, tabCounts[value])}
                </Badge>
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        <Select
          value={selectedOrderId === "all" ? "all" : String(selectedOrderId)}
          onValueChange={(value) =>
            setSelectedOrderId(value === "all" ? "all" : Number(value))
          }
        >
          <SelectTrigger className="h-8 w-full text-xs md:w-60">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{results("tabs.all")}</SelectItem>
            {(ordersQuery.data ?? []).slice(0, TOP_N_ORDERS).map((order) => (
              <SelectItem key={order.id} value={String(order.id)}>
                order#{order.id} · {order.product_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">#</TableHead>
              <TableHead>{results("table.result")}</TableHead>
              <TableHead>{results("table.order")}</TableHead>
              <TableHead className="w-24">{results("table.source")}</TableHead>
              <TableHead className="w-32 text-right">{results("table.perUnit")}</TableHead>
              <TableHead className="w-32 text-right">{results("table.listed")}</TableHead>
              <TableHead className="w-40">{results("table.collected")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoadingResults ? (
              Array.from({ length: 4 }).map((_, i) => (
                <TableRow key={`loading-${i}`}>
                  {Array.from({ length: 7 }).map((__, j) => (
                    <TableCell key={`loading-cell-${j}`}>
                      <Skeleton className="h-4 w-full" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="h-32 text-center">
                  <div className="mx-auto max-w-sm text-xs text-muted-foreground">
                    {common("empty")}
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              filtered.map((result, index) => {
                const isBest = result.rank === 1;
                return (
                  <TableRow key={`${result.order_id}-${result.id}`}>
                    <TableCell className="text-center font-mono text-[10px] text-muted-foreground">
                      {isBest ? (
                        <span className="inline-flex size-5 items-center justify-center rounded-full bg-emerald-500/10 text-[9px] font-semibold text-emerald-700 dark:text-emerald-300">
                          1
                        </span>
                      ) : (
                        <span className="text-muted-foreground/60">{index + 1}</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col gap-0.5">
                        <div className="flex items-center gap-1.5 text-sm font-medium">
                          <span className="truncate">{result.seller_name ?? "—"}</span>
                          <a
                            href={result.product_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-muted-foreground hover:text-primary"
                          >
                            <ExternalLink className="size-3" />
                          </a>
                        </div>
                        <span className="font-mono text-[10px] text-muted-foreground">
                          result#{result.id}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col gap-0.5 text-xs">
                        <span className="font-medium">
                          {result.order?.product_name ?? `order#${result.order_id}`}
                        </span>
                        {result.order?.option_text ? (
                          <span className="text-muted-foreground">
                            {result.order.option_text}
                          </span>
                        ) : null}
                      </div>
                    </TableCell>
                    <TableCell>
                      <SourceBadge source={result.source} />
                    </TableCell>
                    <TableCell className="text-right font-mono font-semibold tabular-nums">
                      {formatCurrencyKRW(locale, toNumber(result.per_unit_price))}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs text-muted-foreground tabular-nums">
                      {formatCurrencyKRW(locale, toNumber(result.listed_price))}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDateTime(locale, result.collected_at)}
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>

      {resultsQueries.some((q) => q.isError) ? (
        <EmptyState
          title={common("error")}
          description={
            resultsQueries.find((q) => q.isError)?.error?.message ?? common("empty")
          }
        />
      ) : null}
    </div>
  );
}
