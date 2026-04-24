"use client";

import type * as React from "react";
import { ThemeProvider as NextThemesProvider } from "next-themes";

import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      <TooltipProvider delayDuration={200}>
        {children}
        <Toaster position="top-right" richColors closeButton />
      </TooltipProvider>
    </NextThemesProvider>
  );
}
