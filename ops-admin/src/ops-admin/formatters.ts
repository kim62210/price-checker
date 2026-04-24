import type { Locale } from '../i18n';

const localeMap: Record<Locale, string> = {
  ko: 'ko-KR',
  en: 'en-US',
};

export function formatCurrency(locale: Locale, value: number): string {
  return new Intl.NumberFormat(localeMap[locale], {
    style: 'currency',
    currency: 'KRW',
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatNumber(locale: Locale, value: number): string {
  return new Intl.NumberFormat(localeMap[locale], {
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatCompactNumber(locale: Locale, value: number): string {
  return new Intl.NumberFormat(localeMap[locale], {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value);
}

export function formatPercent(
  locale: Locale,
  value: number,
  maximumFractionDigits = 1,
  signDisplay: Intl.NumberFormatOptions['signDisplay'] = 'auto',
): string {
  return new Intl.NumberFormat(localeMap[locale], {
    style: 'percent',
    maximumFractionDigits,
    signDisplay,
  }).format(value / 100);
}

export function formatDateTime(
  locale: Locale,
  value: Date | number | string,
  options: Intl.DateTimeFormatOptions = {},
): string {
  const date = value instanceof Date ? value : new Date(value);
  const hasExplicitParts = Object.keys(options).length > 0;
  const formatterOptions = hasExplicitParts
    ? options
    : { dateStyle: 'medium', timeStyle: 'short' } satisfies Intl.DateTimeFormatOptions;

  return new Intl.DateTimeFormat(localeMap[locale], formatterOptions).format(date);
}

export function formatRelativeTime(
  locale: Locale,
  value: Date | number | string,
  now: Date | number | string = new Date(),
): string {
  const target = value instanceof Date ? value : new Date(value);
  const reference = now instanceof Date ? now : new Date(now);
  const diffMilliseconds = target.getTime() - reference.getTime();
  const diffSeconds = Math.round(diffMilliseconds / 1000);

  const formatter = new Intl.RelativeTimeFormat(localeMap[locale], { numeric: 'auto' });
  const absoluteSeconds = Math.abs(diffSeconds);

  if (absoluteSeconds < 60) {
    return formatter.format(diffSeconds, 'second');
  }

  const diffMinutes = Math.round(diffSeconds / 60);
  if (Math.abs(diffMinutes) < 60) {
    return formatter.format(diffMinutes, 'minute');
  }

  const diffHours = Math.round(diffMinutes / 60);
  if (Math.abs(diffHours) < 24) {
    return formatter.format(diffHours, 'hour');
  }

  const diffDays = Math.round(diffHours / 24);
  return formatter.format(diffDays, 'day');
}
