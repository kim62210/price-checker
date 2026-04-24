import { getTranslations } from "next-intl/server";

import { NotificationsView } from "@/components/notifications/notifications-view";
import { PageHeader } from "@/components/shared/page-header";

export default async function NotificationsPage() {
  const t = await getTranslations("notifications");

  return (
    <div className="flex flex-1 flex-col gap-6 p-4 md:gap-8 md:p-6">
      <PageHeader title={t("title")} description={t("description")} />
      <NotificationsView />
    </div>
  );
}
