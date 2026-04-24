const localeMap = {
  ko: "ko-KR",
  en: "en-US",
} as const;

type SupportedLocale = keyof typeof localeMap;

function toIntlLocale(locale: string): string {
  return locale in localeMap ? localeMap[locale as SupportedLocale] : localeMap.ko;
}

export function formatCurrencyKRW(locale: string, value: number): string {
  return new Intl.NumberFormat(toIntlLocale(locale), {
    style: "currency",
    currency: "KRW",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatCompactNumber(locale: string, value: number): string {
  return new Intl.NumberFormat(toIntlLocale(locale), {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

export function formatInteger(locale: string, value: number): string {
  return new Intl.NumberFormat(toIntlLocale(locale), {
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatPercent(
  locale: string,
  value: number,
  maximumFractionDigits = 1,
): string {
  return new Intl.NumberFormat(toIntlLocale(locale), {
    style: "percent",
    maximumFractionDigits,
  }).format(value);
}

export function formatDateTime(
  locale: string,
  value: Date | number | string,
  options: Intl.DateTimeFormatOptions = { dateStyle: "medium", timeStyle: "short" },
): string {
  const date = value instanceof Date ? value : new Date(value);
  return new Intl.DateTimeFormat(toIntlLocale(locale), options).format(date);
}

export function formatRelativeTime(
  locale: string,
  value: Date | number | string,
  now: Date = new Date(),
): string {
  const target = value instanceof Date ? value : new Date(value);
  const diffSeconds = Math.round((target.getTime() - now.getTime()) / 1000);
  const formatter = new Intl.RelativeTimeFormat(toIntlLocale(locale), { numeric: "auto" });

  const absSeconds = Math.abs(diffSeconds);
  if (absSeconds < 60) return formatter.format(diffSeconds, "second");

  const diffMinutes = Math.round(diffSeconds / 60);
  if (Math.abs(diffMinutes) < 60) return formatter.format(diffMinutes, "minute");

  const diffHours = Math.round(diffMinutes / 60);
  if (Math.abs(diffHours) < 24) return formatter.format(diffHours, "hour");

  const diffDays = Math.round(diffHours / 24);
  return formatter.format(diffDays, "day");
}

export function toNumber(value: string | number | null | undefined): number {
  if (value === null || value === undefined) return 0;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}
