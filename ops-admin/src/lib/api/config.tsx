"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import type { ApiClientOptions } from "./client";

export const API_CONFIG_STORAGE_KEY = "lowest-price.ops-admin.api-config";
export const DEFAULT_BACKEND_URL = "http://localhost:8000";

export interface ApiConfig {
  backendUrl: string;
  accessToken: string;
}

interface ApiConfigContextValue {
  config: ApiConfig;
  isHydrated: boolean;
  isAuthorized: boolean;
  setConfig: (config: ApiConfig) => void;
  reset: () => void;
}

const defaultConfig: ApiConfig = {
  backendUrl: DEFAULT_BACKEND_URL,
  accessToken: "",
};

const ApiConfigContext = createContext<ApiConfigContextValue | null>(null);

function readStorage(): ApiConfig {
  if (typeof window === "undefined") return defaultConfig;

  try {
    const raw = window.localStorage.getItem(API_CONFIG_STORAGE_KEY);
    if (!raw) return defaultConfig;
    const parsed = JSON.parse(raw) as Partial<ApiConfig>;
    return {
      backendUrl:
        typeof parsed.backendUrl === "string" && parsed.backendUrl.trim()
          ? parsed.backendUrl.trim()
          : DEFAULT_BACKEND_URL,
      accessToken: typeof parsed.accessToken === "string" ? parsed.accessToken : "",
    };
  } catch {
    return defaultConfig;
  }
}

export function ApiConfigProvider({ children }: { children: React.ReactNode }) {
  const [config, setConfigState] = useState<ApiConfig>(defaultConfig);
  const [isHydrated, setIsHydrated] = useState(false);

  useEffect(() => {
    setConfigState(readStorage());
    setIsHydrated(true);
  }, []);

  const setConfig = useCallback((next: ApiConfig) => {
    setConfigState(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(API_CONFIG_STORAGE_KEY, JSON.stringify(next));
    }
  }, []);

  const reset = useCallback(() => {
    setConfigState(defaultConfig);
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(API_CONFIG_STORAGE_KEY);
    }
  }, []);

  const value = useMemo<ApiConfigContextValue>(
    () => ({
      config,
      isHydrated,
      isAuthorized: Boolean(config.accessToken),
      setConfig,
      reset,
    }),
    [config, isHydrated, setConfig, reset],
  );

  return <ApiConfigContext.Provider value={value}>{children}</ApiConfigContext.Provider>;
}

export function useApiConfig(): ApiConfigContextValue {
  const context = useContext(ApiConfigContext);
  if (!context) {
    throw new Error("useApiConfig must be used within ApiConfigProvider");
  }
  return context;
}

export function toClientOptions(config: ApiConfig): ApiClientOptions {
  return {
    baseUrl: config.backendUrl || DEFAULT_BACKEND_URL,
    accessToken: config.accessToken || null,
  };
}
