"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Beaker, FileUp, GitCompareArrows, Shuffle } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyState } from "@/components/shared/empty-state";

type TabValue = "uploads" | "parseRuns" | "compare" | "regressions";

const TAB_META: Record<TabValue, { icon: typeof FileUp; titleKey: TabValue; descriptionKey: string }> = {
  uploads: {
    icon: FileUp,
    titleKey: "uploads",
    descriptionKey: "파서 테스트용 업로드 데이터와 시도 이력을 추적합니다.",
  },
  parseRuns: {
    icon: Shuffle,
    titleKey: "parseRuns",
    descriptionKey: "내부 파서 버전별 실행 성공률과 재시도 로그를 분리해 관리합니다.",
  },
  compare: {
    icon: GitCompareArrows,
    titleKey: "compare",
    descriptionKey: "Naver/Coupang/수동 업로드 결과를 교차 비교해 편차를 감시합니다.",
  },
  regressions: {
    icon: Beaker,
    titleKey: "regressions",
    descriptionKey: "파서 회귀 케이스와 재현 스냅샷을 기록합니다.",
  },
};

export function ExperimentsView() {
  const experiments = useTranslations("experiments");
  const common = useTranslations("common");
  const [tab, setTab] = useState<TabValue>("uploads");

  return (
    <div className="flex flex-col gap-4">
      <Alert className="border-amber-500/40 bg-amber-500/5 text-amber-700 dark:text-amber-300">
        <Beaker className="size-4" />
        <AlertTitle className="text-xs font-semibold">INTERNAL EXPERIMENT</AlertTitle>
        <AlertDescription className="text-xs">
          실험용 파서와 업로드 데이터는 운영 파이프라인과 분리됩니다. 전용 API 연동 전까지는
          화면 구조만 제공됩니다.
        </AlertDescription>
      </Alert>

      <Tabs value={tab} onValueChange={(value) => setTab(value as TabValue)}>
        <TabsList>
          {(Object.keys(TAB_META) as TabValue[]).map((value) => (
            <TabsTrigger key={value} value={value}>
              {experiments(`tabs.${value}`)}
            </TabsTrigger>
          ))}
        </TabsList>

        {(Object.keys(TAB_META) as TabValue[]).map((value) => {
          const meta = TAB_META[value];
          const Icon = meta.icon;
          return (
            <TabsContent key={value} value={value} className="mt-4">
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Icon className="size-4 text-muted-foreground" />
                    <CardTitle className="text-sm">
                      {experiments(`tabs.${meta.titleKey}`)}
                    </CardTitle>
                  </div>
                  <CardDescription className="text-xs">
                    {meta.descriptionKey}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <EmptyState
                    icon={Icon}
                    title={common("empty")}
                    description="전용 백엔드 엔드포인트 연결 후 활성화됩니다."
                  />
                </CardContent>
              </Card>
            </TabsContent>
          );
        })}
      </Tabs>
    </div>
  );
}
