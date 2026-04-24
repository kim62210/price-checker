"use client";

import { useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Phone } from "lucide-react";

import { Badge } from "@/components/ui/badge";
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
import { useApiConfig } from "@/lib/api/config";
import { useNotificationRecipientsQuery } from "@/lib/api/queries";
import { formatDateTime, formatInteger } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { NotificationRecipientRead } from "@/types/api";

type RecipientTab = "all" | "active" | "inactive";

const TABS: RecipientTab[] = ["all", "active", "inactive"];

function filterByTab(items: NotificationRecipientRead[], tab: RecipientTab) {
  if (tab === "all") return items;
  if (tab === "active") return items.filter((item) => item.is_active);
  return items.filter((item) => !item.is_active);
}

function filterByQuery(items: NotificationRecipientRead[], query: string) {
  if (!query.trim()) return items;
  const needle = query.trim().toLowerCase();
  return items.filter(
    (item) =>
      item.display_name.toLowerCase().includes(needle) ||
      item.phone_e164.toLowerCase().includes(needle) ||
      String(item.id).includes(needle),
  );
}

export function NotificationsView() {
  const notifications = useTranslations("notifications");
  const common = useTranslations("common");
  const locale = useLocale();
  const { isAuthorized, isHydrated } = useApiConfig();
  const [tab, setTab] = useState<RecipientTab>("all");
  const [query, setQuery] = useState("");

  const recipientsQuery = useNotificationRecipientsQuery();

  const filtered = useMemo(() => {
    if (!recipientsQuery.data) return [];
    return filterByQuery(filterByTab(recipientsQuery.data, tab), query);
  }, [recipientsQuery.data, tab, query]);

  const counts = useMemo(() => {
    const base = recipientsQuery.data ?? [];
    return {
      all: base.length,
      active: base.filter((item) => item.is_active).length,
      inactive: base.filter((item) => !item.is_active).length,
    } satisfies Record<RecipientTab, number>;
  }, [recipientsQuery.data]);

  if (!isHydrated) return <Skeleton className="h-[200px] w-full" />;
  if (!isAuthorized) return <NotConnectedState />;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <Tabs value={tab} onValueChange={(value) => setTab(value as RecipientTab)}>
          <TabsList>
            {TABS.map((value) => (
              <TabsTrigger key={value} value={value} className="capitalize">
                {value === "all"
                  ? notifications("tabs.all")
                  : value === "active"
                    ? notifications("kpi.activeRecipients")
                    : notifications("tabs.failed")}
                <Badge
                  variant="outline"
                  className="ml-2 h-4 min-w-4 rounded-full px-1 font-mono text-[10px]"
                >
                  {formatInteger(locale, counts[value])}
                </Badge>
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        <Input
          type="search"
          placeholder={notifications("table.recipient")}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="h-8 w-full text-xs md:w-64"
        />
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-16">#</TableHead>
              <TableHead>{notifications("table.recipient")}</TableHead>
              <TableHead>{notifications("table.channel")}</TableHead>
              <TableHead className="w-24">{notifications("table.status")}</TableHead>
              <TableHead className="w-28">Shop / User</TableHead>
              <TableHead className="w-40">{notifications("table.sent")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {recipientsQuery.isLoading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <TableRow key={`loading-${i}`}>
                  {Array.from({ length: 6 }).map((__, j) => (
                    <TableCell key={`cell-${j}`}>
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
              filtered.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    #{item.id}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col gap-0.5">
                      <span className="text-sm font-medium">{item.display_name}</span>
                      <span className="flex items-center gap-1 font-mono text-[10px] text-muted-foreground">
                        <Phone className="size-2.5" />
                        {item.phone_e164}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="font-mono text-[10px]">
                      알림톡 · SMS
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <span
                      className={cn(
                        "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-mono text-[10px] font-medium",
                        item.is_active
                          ? "bg-emerald-500/10 text-emerald-700 ring-1 ring-emerald-500/20 dark:text-emerald-300"
                          : "bg-muted text-muted-foreground ring-1 ring-border",
                      )}
                    >
                      <span className="size-1.5 rounded-full bg-current" />
                      {item.is_active
                        ? notifications("tabs.delivered")
                        : notifications("tabs.failed")}
                    </span>
                  </TableCell>
                  <TableCell className="font-mono text-[10px] text-muted-foreground">
                    {item.shop_id ? `shop#${item.shop_id}` : ""}
                    {item.shop_id && item.user_id ? " · " : ""}
                    {item.user_id ? `user#${item.user_id}` : ""}
                    {!item.shop_id && !item.user_id ? "—" : ""}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {formatDateTime(locale, item.updated_at)}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {recipientsQuery.isError ? (
        <EmptyState
          title={common("error")}
          description={String(recipientsQuery.error?.message ?? common("empty"))}
        />
      ) : null}
    </div>
  );
}
