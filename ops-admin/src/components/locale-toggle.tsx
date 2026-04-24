"use client";

import { useTransition } from "react";
import { Languages } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { setLocaleAction } from "@/i18n/actions";
import { locales, type Locale } from "@/i18n/config";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function LocaleToggle() {
  const t = useTranslations("locale");
  const current = useLocale() as Locale;
  const [isPending, startTransition] = useTransition();

  const handleChange = (next: Locale) => {
    if (next === current) return;
    startTransition(() => {
      void setLocaleAction(next);
    });
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={t("toggle")}
          disabled={isPending}
          className="text-muted-foreground hover:text-foreground"
        >
          <Languages className="size-4" />
          <span className="sr-only">{t("toggle")}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[10rem]">
        <DropdownMenuLabel className="text-xs text-muted-foreground">
          {t("toggle")}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {locales.map((locale) => (
          <DropdownMenuCheckboxItem
            key={locale}
            checked={current === locale}
            onCheckedChange={() => handleChange(locale)}
          >
            {t(locale)}
          </DropdownMenuCheckboxItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
