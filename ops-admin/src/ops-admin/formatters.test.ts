import { describe, expect, it } from 'vitest';

import { formatCompactNumber, formatCurrency, formatDateTime, formatPercent, formatRelativeTime } from './formatters';

describe('ops admin formatters', () => {
  it('formats KRW values per locale', () => {
    expect(formatCurrency('ko', 18200)).toContain('₩');
    expect(formatCurrency('en', 18200)).toContain('₩');
  });

  it('formats compact numbers for large counts', () => {
    expect(formatCompactNumber('en', 8400)).not.toBe('8400');
  });

  it('formats percentages with locale-aware symbols', () => {
    expect(formatPercent('en', 96.8, 1)).toContain('%');
    expect(formatPercent('ko', 96.8, 1)).toContain('%');
  });

  it('formats dates and relative time using Intl', () => {
    const base = '2026-04-24T10:14:08Z';
    expect(formatDateTime('en', base, { timeZone: 'UTC', year: 'numeric', month: 'short', day: 'numeric' })).toContain('2026');
    expect(formatRelativeTime('en', '2026-04-24T10:13:08Z', base)).toContain('minute');
  });
});
