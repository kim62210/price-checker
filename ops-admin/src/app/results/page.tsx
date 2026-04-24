import { getTranslations } from "next-intl/server";

import { ResultsView } from "@/components/results/results-view";
import { PageHeader } from "@/components/shared/page-header";

export default async function ResultsPage() {
  const t = await getTranslations("results");

  return (
    <div className="flex flex-1 flex-col gap-6 p-4 md:gap-8 md:p-6">
      <PageHeader title={t("title")} description={t("description")} />
      <ResultsView />
    </div>
  );
}
