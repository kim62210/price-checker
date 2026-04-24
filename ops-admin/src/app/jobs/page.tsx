import { getTranslations } from "next-intl/server";

import { JobsView } from "@/components/jobs/jobs-view";
import { PageHeader } from "@/components/shared/page-header";

export default async function JobsPage() {
  const t = await getTranslations("jobs");

  return (
    <div className="flex flex-1 flex-col gap-6 p-4 md:gap-8 md:p-6">
      <PageHeader title={t("title")} description={t("description")} />
      <JobsView />
    </div>
  );
}
