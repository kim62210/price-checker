"use client";

import { useLocale, useTranslations } from "next-intl";
import { ArrowDown, ExternalLink } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { OrderStatusBadge, SourceBadge } from "@/components/shared/status-badge";
import { useOrderQuery, useOrderResultsQuery } from "@/lib/api/queries";
import { formatCurrencyKRW, formatDateTime, formatInteger, toNumber } from "@/lib/format";

interface OrderDetailSheetProps {
  orderId: number | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function OrderDetailSheet({ orderId, open, onOpenChange }: OrderDetailSheetProps) {
  const locale = useLocale();
  const common = useTranslations("common");
  const results = useTranslations("results");
  const detail = useTranslations("jobs.detail");
  const orderQuery = useOrderQuery(orderId);
  const resultsQuery = useOrderResultsQuery(orderId);

  const order = orderQuery.data;
  const bestResult = resultsQuery.data?.[0];

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader className="space-y-2 border-b">
          <div className="flex items-center gap-2">
            <SheetTitle className="text-base">
              {orderQuery.isLoading ? <Skeleton className="h-5 w-40" /> : order?.product_name}
            </SheetTitle>
            {order ? <OrderStatusBadge status={order.status} /> : null}
          </div>
          <SheetDescription className="text-xs">
            {orderId !== null ? (
              <span className="font-mono text-muted-foreground">order#{orderId}</span>
            ) : null}
            {order?.option_text ? (
              <span className="ml-2 text-muted-foreground">· {order.option_text}</span>
            ) : null}
          </SheetDescription>
        </SheetHeader>

        <div className="space-y-5 px-5 pb-5">
          <section>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {detail("summary")}
            </h3>
            {orderQuery.isLoading || !order ? (
              <Skeleton className="h-20 w-full" />
            ) : (
              <dl className="grid grid-cols-2 gap-3 text-xs">
                <Meta label={detail("quantity")}>
                  <span className="font-mono tabular-nums">
                    {formatInteger(locale, order.quantity)} {order.unit}
                  </span>
                </Meta>
                <Meta label={detail("targetUnitPrice")}>
                  <span className="font-mono tabular-nums">
                    {order.target_unit_price !== null
                      ? formatCurrencyKRW(locale, toNumber(order.target_unit_price))
                      : "—"}
                  </span>
                </Meta>
                <Meta label={detail("shop")}>
                  <span className="font-mono">shop#{order.shop_id}</span>
                </Meta>
                <Meta label={detail("createdAt")}>
                  {formatDateTime(locale, order.created_at)}
                </Meta>
              </dl>
            )}
          </section>

          <Separator />

          <section>
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {results("title")}
              </h3>
              {bestResult ? (
                <Badge variant="outline" className="gap-1 font-mono text-[10px]">
                  <ArrowDown className="size-3" />
                  {formatCurrencyKRW(locale, toNumber(bestResult.per_unit_price))}
                </Badge>
              ) : null}
            </div>

            {resultsQuery.isLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : resultsQuery.data && resultsQuery.data.length > 0 ? (
              <ul className="space-y-2">
                {resultsQuery.data.slice(0, 8).map((result) => (
                  <li
                    key={result.id}
                    className="flex items-start justify-between gap-3 rounded-md border p-3 text-xs"
                  >
                    <div className="flex min-w-0 flex-col gap-1">
                      <div className="flex items-center gap-2">
                        <SourceBadge source={result.source} />
                        <span className="truncate font-medium">
                          {result.seller_name ?? "—"}
                        </span>
                      </div>
                      <a
                        href={result.product_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-[10px] text-primary hover:underline"
                      >
                        <ExternalLink className="size-3" />
                        <span className="truncate">{result.product_url}</span>
                      </a>
                    </div>
                    <div className="text-right">
                      <div className="font-mono font-semibold tabular-nums">
                        {formatCurrencyKRW(locale, toNumber(result.per_unit_price))}
                      </div>
                      <div className="text-[10px] text-muted-foreground">
                        {results("table.listed")}: {formatCurrencyKRW(locale, toNumber(result.listed_price))}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="rounded-md border border-dashed px-4 py-6 text-center text-xs text-muted-foreground">
                {common("empty")}
              </div>
            )}
          </section>
        </div>
      </SheetContent>
    </Sheet>
  );
}

function Meta({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium">{children}</dd>
    </div>
  );
}
