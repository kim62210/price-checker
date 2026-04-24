import { describe, expect, it } from 'vitest';
import type { ComparisonResult, OrderItem } from '../types/procurement';
import {
  MAX_ORDER_ITEMS,
  buildMockComparison,
  parsePastedRows,
  sortResultsByInputOrder,
  statusMeta,
} from './procurement';

function result(overrides: Partial<ComparisonResult>): ComparisonResult {
  return {
    id: 'r',
    orderItemId: 'a',
    productName: '상품',
    platform: 'coupang',
    optionText: '옵션',
    sellerName: '셀러',
    listedPrice: 1000,
    shippingFee: 0,
    unitCount: 1,
    unit: '개',
    unitPrice: 1000,
    unitPriceConfidence: 'high',
    productUrl: 'https://example.com',
    status: 'ok',
    capturedAt: '2026-04-23T00:00:00.000Z',
    ...overrides,
  };
}

describe('parsePastedRows', () => {
  it('parses Excel-style tab separated rows', () => {
    const parsed = parsePastedRows('콜라 500ml\t12\n과자\t5');

    expect(parsed.truncated).toBe(false);
    expect(parsed.items).toMatchObject([
      { name: '콜라 500ml', quantity: 12, unit: '개' },
      { name: '과자', quantity: 5, unit: '개' },
    ]);
  });

  it('caps pasted rows at the 50-item UX limit', () => {
    const text = Array.from({ length: 55 }, (_, index) => `상품${index + 1}\t1`).join('\n');
    const parsed = parsePastedRows(text);

    expect(parsed.truncated).toBe(true);
    expect(parsed.items).toHaveLength(MAX_ORDER_ITEMS);
    expect(parsed.items.at(-1)?.name).toBe('상품50');
  });
});

describe('sortResultsByInputOrder', () => {
  it('keeps input grouping and pushes null unit prices to the end of each group', () => {
    const items: Pick<OrderItem, 'id'>[] = [{ id: 'cola' }, { id: 'snack' }];
    const sorted = sortResultsByInputOrder([
      result({ id: 'snack-null', orderItemId: 'snack', unitPrice: null }),
      result({ id: 'cola-high', orderItemId: 'cola', unitPrice: 1200 }),
      result({ id: 'cola-low', orderItemId: 'cola', unitPrice: 900 }),
      result({ id: 'snack-price', orderItemId: 'snack', unitPrice: 300 }),
    ], items);

    expect(sorted.map((item) => item.id)).toEqual([
      'cola-low',
      'cola-high',
      'snack-price',
      'snack-null',
    ]);
  });
});

describe('statusMeta', () => {
  it('returns user-facing copy for login-required status', () => {
    expect(statusMeta('login-required')).toMatchObject({
      label: '로그인 필요',
      tone: 'warning',
    });
  });
});

describe('buildMockComparison', () => {
  it('creates two platform results per normalized input item', () => {
    const results = buildMockComparison([
      { id: 'cola', name: '콜라', quantity: 12, unit: '개', targetUnitPrice: 1000 },
      { id: 'blank', name: '   ', quantity: 1, unit: '개' },
    ]);

    expect(results).toHaveLength(2);
    expect(results.every((item) => item.orderItemId === 'cola')).toBe(true);
  });
});
