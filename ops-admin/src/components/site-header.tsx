"use client";

import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { Search } from "lucide-react";

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { ConnectionBadge } from "@/components/connection-badge";
import { LocaleToggle } from "@/components/locale-toggle";
import { ThemeToggle } from "@/components/theme-toggle";
import { allNavItems } from "@/lib/nav";

function resolveItemKey(pathname: string) {
  if (pathname === "/") return "dashboard" as const;
  const match = allNavItems.find(
    (item) => item.href !== "/" && (pathname === item.href || pathname.startsWith(`${item.href}/`)),
  );
  return match?.key ?? null;
}

export function SiteHeader() {
  const pathname = usePathname();
  const app = useTranslations("app");
  const nav = useTranslations("nav");
  const itemKey = resolveItemKey(pathname);
  const isRoot = pathname === "/";
  const title = itemKey ? nav(`items.${itemKey}.title`) : app("brand");

  return (
    <header className="sticky top-0 z-40 flex h-14 shrink-0 items-center gap-2 border-b bg-background/80 px-4 backdrop-blur-md lg:px-6">
      <SidebarTrigger className="-ml-1" />
      <Separator orientation="vertical" className="mr-2 h-5" />

      <Breadcrumb className="hidden sm:block">
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink href="/">{app("brand")}</BreadcrumbLink>
          </BreadcrumbItem>
          {!isRoot && (
            <>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage>{title}</BreadcrumbPage>
              </BreadcrumbItem>
            </>
          )}
        </BreadcrumbList>
      </Breadcrumb>

      <div className="flex-1" />

      <div className="relative hidden md:block">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="search"
          placeholder={app("search.placeholder")}
          className="h-8 w-56 pl-8 text-xs"
          aria-label={app("search.ariaLabel")}
        />
        <kbd className="pointer-events-none absolute top-1/2 right-2 hidden -translate-y-1/2 rounded border bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground sm:inline-flex">
          {app("search.shortcut")}
        </kbd>
      </div>

      <ConnectionBadge />
      <LocaleToggle />
      <ThemeToggle />
    </header>
  );
}
