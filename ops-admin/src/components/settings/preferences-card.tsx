"use client";

import { useTranslations, useLocale } from "next-intl";
import { useTheme } from "next-themes";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { LocaleToggle } from "@/components/locale-toggle";
import { ThemeToggle } from "@/components/theme-toggle";
import type { Locale } from "@/i18n/config";

export function PreferencesCard() {
  const settings = useTranslations("settings.preferences");
  const locale = useLocale() as Locale;
  const localeT = useTranslations("locale");
  const themeT = useTranslations("theme");
  const { theme } = useTheme();
  const currentTheme = theme ?? "system";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{settings("title")}</CardTitle>
        <CardDescription className="text-xs">
          헤더의 토글과 동일하게 현재 사용자 환경에만 적용됩니다.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex flex-col gap-1">
            <Label className="text-xs">{settings("theme")}</Label>
            <Badge variant="outline" className="w-fit font-mono text-[10px] capitalize">
              {themeT(currentTheme as "light" | "dark" | "system")}
            </Badge>
          </div>
          <ThemeToggle />
        </div>

        <div className="flex items-center justify-between">
          <div className="flex flex-col gap-1">
            <Label className="text-xs">{settings("locale")}</Label>
            <Badge variant="outline" className="w-fit font-mono text-[10px]">
              {localeT(locale)}
            </Badge>
          </div>
          <LocaleToggle />
        </div>
      </CardContent>
    </Card>
  );
}
