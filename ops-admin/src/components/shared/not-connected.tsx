"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { ArrowRight, KeyRound } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/shared/empty-state";

export function NotConnectedState() {
  const auth = useTranslations("auth");
  const nav = useTranslations("nav");

  return (
    <EmptyState
      icon={KeyRound}
      title={auth("title")}
      description={auth("fallback")}
      action={
        <Button asChild size="sm">
          <Link href="/settings">
            {nav("items.settings.title")}
            <ArrowRight className="size-3" />
          </Link>
        </Button>
      }
    />
  );
}
