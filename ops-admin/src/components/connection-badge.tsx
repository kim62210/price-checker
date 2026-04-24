"use client";

import { useTranslations } from "next-intl";
import { Circle, Database, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { useApiConfig } from "@/lib/api/config";
import { useTenantQuery } from "@/lib/api/queries";
import { cn } from "@/lib/utils";

export function ConnectionBadge() {
  const app = useTranslations("app");
  const { isAuthorized, isHydrated } = useApiConfig();
  const tenantQuery = useTenantQuery();

  if (!isHydrated) {
    return (
      <Badge variant="outline" className="h-7 gap-1.5 px-2 font-medium">
        <Circle className="size-2.5 animate-pulse fill-muted-foreground/40 text-muted-foreground/40" />
        <span className="text-xs">…</span>
      </Badge>
    );
  }

  if (!isAuthorized) {
    return (
      <Badge
        variant="outline"
        className="h-7 gap-1.5 px-2 font-medium text-muted-foreground"
      >
        <Sparkles className="size-3" />
        <span className="text-xs">{app("dataSource.sample")}</span>
      </Badge>
    );
  }

  const state = tenantQuery.isError
    ? "error"
    : tenantQuery.isLoading
      ? "loading"
      : "connected";

  return (
    <Badge
      variant="outline"
      className={cn(
        "h-7 gap-1.5 px-2 font-medium",
        state === "connected" && "border-emerald-500/40 text-emerald-700 dark:text-emerald-300",
        state === "error" && "border-destructive/40 text-destructive",
        state === "loading" && "text-muted-foreground",
      )}
    >
      <Database className="size-3" />
      <span className="text-xs">{app("dataSource.live")}</span>
      {state === "connected" && tenantQuery.data ? (
        <span className="text-xs text-muted-foreground">· {tenantQuery.data.name}</span>
      ) : null}
    </Badge>
  );
}
