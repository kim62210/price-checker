export function formatKrw(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '-';
  }
  return new Intl.NumberFormat('ko-KR', {
    style: 'currency',
    currency: 'KRW',
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatUnitPrice(value: number | null, unit: string): string {
  if (value === null || Number.isNaN(value)) {
    return '계산 불가';
  }
  const suffix = unit === 'g' ? '100g' : unit === 'ml' ? '100ml' : unit || '개';
  const multiplier = unit === 'g' || unit === 'ml' ? 100 : 1;
  return `${formatKrw(Math.round(value * multiplier))}/${suffix}`;
}

export function formatPercent(value: number): string {
  return `${Math.max(0, Math.min(100, Math.round(value)))}%`;
}
