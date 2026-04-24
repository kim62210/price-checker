import { getTranslations } from "next-intl/server";

import { ExperimentsView } from "@/components/experiments/experiments-view";
import { PageHeader } from "@/components/shared/page-header";

export default async function ExperimentsPage() {
  const t = await getTranslations("experiments");

  return (
    <div className="flex flex-1 flex-col gap-6 p-4 md:gap-8 md:p-6">
      <PageHeader title={t("title")} description={t("description")} />
      <ExperimentsView />
    </div>
  );
}
