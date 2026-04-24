import { createContext, createElement, useContext, useEffect, useMemo, useState } from 'react';

import type { ReactNode } from 'react';

import enMessages from './messages/en.json';
import koMessages from './messages/ko.json';
import {
  formatCompactNumber,
  formatCurrency,
  formatDateTime,
  formatNumber,
  formatPercent,
  formatRelativeTime,
} from '../ops-admin/formatters';

export const locales = ['ko', 'en'] as const;

export type Locale = (typeof locales)[number];
export type MessageKey = keyof typeof koMessages;
export type MessageValues = Record<string, number | string>;

const localeStorageKey = 'lowest-price.ops-admin.locale';

export const localeMessages = {
  ko: koMessages,
  en: enMessages,
} as const;

interface I18nContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: MessageKey, values?: MessageValues) => string;
  formatCurrency: (value: number) => string;
  formatNumber: (value: number) => string;
  formatCompactNumber: (value: number) => string;
  formatDateTime: (value: Date | number | string, options?: Intl.DateTimeFormatOptions) => string;
  formatPercent: (value: number, maximumFractionDigits?: number, signDisplay?: Intl.NumberFormatOptions['signDisplay']) => string;
  formatRelativeTime: (value: Date | number | string, now?: Date | number | string) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

function getStoredLocale(): Locale {
  if (typeof window === 'undefined') {
    return 'ko';
  }

  const stored = window.localStorage.getItem(localeStorageKey);
  return isLocale(stored) ? stored : 'ko';
}

export function isLocale(value: string | null | undefined): value is Locale {
  return locales.includes(value as Locale);
}

function interpolate(template: string, values?: MessageValues): string {
  if (!values) {
    return template;
  }

  return template.replace(/\{(\w+)\}/g, (match, placeholder: string) => {
    const value = values[placeholder];
    return value === undefined ? match : String(value);
  });
}

export function translate(locale: Locale, key: MessageKey, values?: MessageValues): string {
  const dictionary = localeMessages[locale] as Record<MessageKey, string>;
  return interpolate(dictionary[key] ?? String(key), values);
}

export function getMissingMessageKeys(base: Record<string, string>, target: Record<string, string>): string[] {
  return Object.keys(base).filter((key) => !(key in target));
}

interface I18nProviderProps {
  children: ReactNode;
}

export function I18nProvider({ children }: I18nProviderProps) {
  const [locale, setLocale] = useState<Locale>(getStoredLocale);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(localeStorageKey, locale);
    }
  }, [locale]);

  const value = useMemo<I18nContextValue>(() => ({
    locale,
    setLocale,
    t: (key, values) => translate(locale, key, values),
    formatCurrency: (value) => formatCurrency(locale, value),
    formatNumber: (value) => formatNumber(locale, value),
    formatCompactNumber: (value) => formatCompactNumber(locale, value),
    formatDateTime: (value, options) => formatDateTime(locale, value, options),
    formatPercent: (value, maximumFractionDigits, signDisplay) => formatPercent(locale, value, maximumFractionDigits, signDisplay),
    formatRelativeTime: (value, now) => formatRelativeTime(locale, value, now),
  }), [locale]);

  return createElement(I18nContext.Provider, { value }, children);
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useI18n must be used within I18nProvider');
  }
  return context;
}
