"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { CheckCircle2, KeyRound, Link2, Loader2, XCircle } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/client";
import { DEFAULT_BACKEND_URL, toClientOptions, useApiConfig } from "@/lib/api/config";
import { fetchCurrentUser, fetchTenant } from "@/lib/api/procurement";

type TestState =
  | { status: "idle" }
  | { status: "testing" }
  | { status: "success"; tenant: string; user: string }
  | { status: "error"; message: string };

export function ApiConfigCard() {
  const t = useTranslations("settings.api");
  const auth = useTranslations("auth");
  const common = useTranslations("common");
  const queryClient = useQueryClient();
  const { config, setConfig, reset } = useApiConfig();

  const [backendUrl, setBackendUrl] = useState(config.backendUrl);
  const [accessToken, setAccessToken] = useState(config.accessToken);
  const [testState, setTestState] = useState<TestState>({ status: "idle" });

  useEffect(() => {
    setBackendUrl(config.backendUrl);
    setAccessToken(config.accessToken);
  }, [config]);

  const handleSave = () => {
    const next = {
      backendUrl: backendUrl.trim() || DEFAULT_BACKEND_URL,
      accessToken: accessToken.trim(),
    };
    setConfig(next);
    queryClient.invalidateQueries();
    toast.success(t("saved"));
  };

  const handleTest = async () => {
    const next = {
      backendUrl: backendUrl.trim() || DEFAULT_BACKEND_URL,
      accessToken: accessToken.trim(),
    };
    setTestState({ status: "testing" });
    try {
      const options = toClientOptions(next);
      const [tenant, user] = await Promise.all([
        fetchTenant(options),
        fetchCurrentUser(options),
      ]);
      setTestState({
        status: "success",
        tenant: tenant.name,
        user: user.email,
      });
      setConfig(next);
      queryClient.invalidateQueries();
      toast.success(t("saved"), { description: tenant.name });
    } catch (error) {
      const message =
        error instanceof ApiError
          ? `${error.status} · ${error.message}`
          : error instanceof Error
            ? error.message
            : String(error);
      const isUnauthorized = error instanceof ApiError && error.status === 401;
      setTestState({
        status: "error",
        message: isUnauthorized ? auth("errors.invalidToken") : message,
      });
    }
  };

  const handleReset = () => {
    reset();
    setBackendUrl(DEFAULT_BACKEND_URL);
    setAccessToken("");
    setTestState({ status: "idle" });
    queryClient.invalidateQueries();
    toast.success(t("cleared"));
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t("title")}</CardTitle>
        <CardDescription className="text-xs">{auth("description")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-2">
          <Label htmlFor="backend-url" className="text-xs">
            {t("backendUrl")}
          </Label>
          <div className="relative">
            <Link2 className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="backend-url"
              type="url"
              value={backendUrl}
              onChange={(e) => setBackendUrl(e.target.value)}
              placeholder={DEFAULT_BACKEND_URL}
              className="pl-8 font-mono text-xs"
              autoComplete="off"
              spellCheck={false}
            />
          </div>
        </div>

        <div className="grid gap-2">
          <Label htmlFor="access-token" className="text-xs">
            {t("accessToken")}
          </Label>
          <div className="relative">
            <KeyRound className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="access-token"
              type="password"
              value={accessToken}
              onChange={(e) => setAccessToken(e.target.value)}
              placeholder="eyJhbGciOi…"
              className="pl-8 font-mono text-xs"
              autoComplete="off"
              spellCheck={false}
            />
          </div>
        </div>

        {testState.status === "success" ? (
          <Alert className="border-emerald-500/40 bg-emerald-500/5 text-emerald-700 dark:text-emerald-300">
            <CheckCircle2 className="size-4" />
            <AlertTitle className="text-xs font-semibold">{t("saved")}</AlertTitle>
            <AlertDescription className="text-xs">
              {testState.tenant} · {testState.user}
            </AlertDescription>
          </Alert>
        ) : null}
        {testState.status === "error" ? (
          <Alert variant="destructive">
            <XCircle className="size-4" />
            <AlertTitle className="text-xs font-semibold">{common("error")}</AlertTitle>
            <AlertDescription className="text-xs">{testState.message}</AlertDescription>
          </Alert>
        ) : null}

        <div className="flex flex-wrap gap-2 pt-1">
          <Button
            onClick={handleTest}
            size="sm"
            disabled={testState.status === "testing"}
          >
            {testState.status === "testing" ? (
              <Loader2 className="size-3 animate-spin" />
            ) : (
              <CheckCircle2 className="size-3" />
            )}
            {t("connect")}
          </Button>
          <Button onClick={handleSave} size="sm" variant="secondary">
            {t("save")}
          </Button>
          <Button onClick={handleReset} size="sm" variant="ghost">
            {t("reset")}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
