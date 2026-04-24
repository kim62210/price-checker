import { getTranslations } from "next-intl/server";

import { ApiConfigCard } from "@/components/settings/api-config-card";
import { PreferencesCard } from "@/components/settings/preferences-card";

export default async function SettingsPage() {
  const t = await getTranslations("settings");

  return (
    <div className="flex flex-1 flex-col gap-6 p-4 md:gap-8 md:p-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("description")}</p>
      </div>

      <div className="grid max-w-4xl gap-4 md:grid-cols-2">
        <ApiConfigCard />
        <PreferencesCard />
      </div>
    </div>
  );
}
