import { cn } from "@/lib/utils";

import type { OrderStatus, ResultSource } from "@/types/api";

const statusTone: Record<OrderStatus, string> = {
  draft: "bg-muted text-muted-foreground",
  collecting: "bg-blue-500/10 text-blue-700 dark:text-blue-300 ring-1 ring-blue-500/20",
  completed:
    "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 ring-1 ring-emerald-500/20",
  cancelled: "bg-destructive/10 text-destructive ring-1 ring-destructive/20",
};

const sourceTone: Record<ResultSource, string> = {
  naver: "bg-green-500/10 text-green-700 dark:text-green-300 ring-1 ring-green-500/20",
  coupang:
    "bg-orange-500/10 text-orange-700 dark:text-orange-300 ring-1 ring-orange-500/20",
  manual: "bg-muted text-muted-foreground ring-1 ring-border",
};

export function OrderStatusBadge({ status }: { status: OrderStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-mono text-[10px] font-medium capitalize",
        statusTone[status],
      )}
    >
      <span className="size-1.5 rounded-full bg-current" />
      {status}
    </span>
  );
}

export function SourceBadge({ source }: { source: ResultSource }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-1.5 py-0.5 font-mono text-[10px] font-medium capitalize",
        sourceTone[source],
      )}
    >
      {source}
    </span>
  );
}
