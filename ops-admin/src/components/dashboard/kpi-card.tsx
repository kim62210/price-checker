"use client";

import type { LucideIcon } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface KpiCardProps {
  label: string;
  value: string;
  helper?: string;
  icon?: LucideIcon;
  trend?: "up" | "down" | "flat";
  trendLabel?: string;
  isLoading?: boolean;
  className?: string;
}

export function KpiCard({
  label,
  value,
  helper,
  icon: Icon,
  trend,
  trendLabel,
  isLoading,
  className,
}: KpiCardProps) {
  return (
    <Card className={cn("relative overflow-hidden", className)}>
      <CardHeader className="flex flex-row items-start justify-between gap-2 pb-1">
        <CardDescription className="text-xs text-muted-foreground">{label}</CardDescription>
        {Icon ? <Icon className="size-4 text-muted-foreground" /> : null}
      </CardHeader>
      <CardContent className="pb-3">
        {isLoading ? (
          <Skeleton className="h-7 w-24" />
        ) : (
          <CardTitle className="text-2xl font-semibold tracking-tight tabular-nums">
            {value}
          </CardTitle>
        )}
        {helper || trendLabel ? (
          <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
            {trend ? (
              <span
                className={cn(
                  "inline-flex items-center rounded px-1 py-0.5 text-[10px] font-medium",
                  trend === "up" && "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
                  trend === "down" && "bg-destructive/10 text-destructive",
                  trend === "flat" && "bg-muted text-muted-foreground",
                )}
              >
                {trendLabel ?? ""}
              </span>
            ) : null}
            {helper ? <span>{helper}</span> : null}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
