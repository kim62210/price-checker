import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { ArrowRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { navGroups } from "@/lib/nav";

const KPI_KEYS = ["activeJobs", "savings24h", "alimtalkRate", "activeRecipients"] as const;

export default async function DashboardHome() {
  const dashboard = await getTranslations("dashboard");
  const app = await getTranslations("app");
  const nav = await getTranslations("nav");
  const items = navGroups.flatMap((group) => group.items).filter((item) => item.href !== "/");

  return (
    <div className="flex flex-1 flex-col gap-6 p-4 md:gap-8 md:p-6">
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-semibold tracking-tight">{dashboard("title")}</h1>
          <Badge variant="outline" className="font-mono text-[10px]">
            {app("environment")}
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">{dashboard("description")}</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {KPI_KEYS.map((key) => (
          <Card key={key}>
            <CardHeader className="pb-2">
              <CardDescription>{dashboard(`kpi.${key}`)}</CardDescription>
              <CardTitle className="text-2xl font-semibold tabular-nums">—</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">{dashboard("kpi.apiPending")}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div>
        <h2 className="mb-3 text-sm font-medium text-muted-foreground">
          {dashboard("quickLinks")}
        </h2>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {items.map((item) => {
            const Icon = item.icon;
            return (
              <Card
                key={item.href}
                className="transition-all hover:border-ring/50 hover:shadow-xs"
              >
                <CardHeader>
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
                <CardFooter className="pt-0">
                  <Link
                    href={item.href}
                    className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                  >
                    {dashboard("goTo")} <ArrowRight className="size-3" />
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
