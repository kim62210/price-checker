import type {
  ComparisonResult,
  Confidence,
  MonthlySaving,
  OrderItem,
  Platform,
  ProcurementProgress,
  RecentOrder,
  ReportMetric,
  WorkflowStatus,
} from '../types/procurement';
import { formatKrw } from './format';

export const MAX_ORDER_ITEMS = 50;

const DEFAULT_RECENT_ORDER_ITEMS: OrderItem[] = [
  { id: 'recent-cola', name: '콜라 500ml', quantity: 12, unit: '개', targetUnitPrice: 950 },
  { id: 'recent-water', name: '생수 2L', quantity: 24, unit: '개', targetUnitPrice: 420 },
  { id: 'recent-snack', name: '스낵 대용량', quantity: 8, unit: '봉', targetUnitPrice: 1600 },
];

export const recentOrders: RecentOrder[] = [
  {
    id: 'last-monday',
    label: '지난주 월요일 발주',
    createdAt: '2026-04-20',
    items: DEFAULT_RECENT_ORDER_ITEMS,
  },
  {
    id: 'monthly-core',
    label: '월초 기본 발주',
    createdAt: '2026-04-01',
    items: [
      { id: 'recent-tissue', name: '물티슈 100매', quantity: 20, unit: '팩', targetUnitPrice: 1100 },
      { id: 'recent-coffee', name: '아메리카노 캔', quantity: 30, unit: '개', targetUnitPrice: 780 },
    ],
  },
];

function slugify(input: string): string {
  return input
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9가-힣]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 32) || 'item';
}

export function createEmptyItem(index: number): OrderItem {
  return {
    id: `manual-${Date.now()}-${index}`,
    name: '',
    quantity: 1,
    unit: '개',
  };
}

export function parsePastedRows(text: string): { items: OrderItem[]; truncated: boolean } {
  const rows = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  const parsed = rows.map((line, index) => {
    const cells = line.split(/\t|,{1}| {2,}/).map((cell) => cell.trim()).filter(Boolean);
    const name = cells[0] ?? '';
    const quantityCandidate = Number.parseInt(cells[1] ?? '1', 10);
    const unit = cells[2] && Number.isNaN(Number(cells[2])) ? cells[2] : '개';
    const targetCandidate = Number.parseFloat(cells[3] ?? cells[2] ?? '');
    return {
      id: `paste-${index + 1}-${slugify(name)}`,
      name,
      quantity: Number.isFinite(quantityCandidate) && quantityCandidate > 0 ? quantityCandidate : 1,
      unit,
      targetUnitPrice: Number.isFinite(targetCandidate) && targetCandidate > 0 ? targetCandidate : undefined,
    } satisfies OrderItem;
  }).filter((item) => item.name.length > 0);

  return {
    items: parsed.slice(0, MAX_ORDER_ITEMS),
    truncated: parsed.length > MAX_ORDER_ITEMS,
  };
}

export function cloneOrderItems(items: OrderItem[], prefix = 'clone'): OrderItem[] {
  return items.slice(0, MAX_ORDER_ITEMS).map((item, index) => ({
    ...item,
    id: `${prefix}-${index + 1}-${slugify(item.name)}`,
  }));
}

export function normalizeOrderItems(items: OrderItem[]): { items: OrderItem[]; truncated: boolean } {
  const cleaned = items
    .map((item) => ({
      ...item,
      name: item.name.trim(),
      quantity: Math.max(1, Math.floor(item.quantity || 1)),
      unit: item.unit.trim() || '개',
      targetUnitPrice:
        item.targetUnitPrice !== undefined && item.targetUnitPrice >= 0
          ? item.targetUnitPrice
          : undefined,
    }))
    .filter((item) => item.name.length > 0);

  return {
    items: cleaned.slice(0, MAX_ORDER_ITEMS),
    truncated: cleaned.length > MAX_ORDER_ITEMS,
  };
}

function platformLabel(platform: Platform): string {
  switch (platform) {
    case 'coupang':
      return '쿠팡';
    case 'naver':
      return '네이버';
    case 'manual':
      return '수동';
  }
}

function confidenceFor(index: number, platform: Platform): Confidence {
  if (platform === 'manual') return 'medium';
  return index % 4 === 2 ? 'low' : 'high';
}

export function buildMockComparison(
  items: OrderItem[],
  backendOrderIds: Partial<Record<string, number>> = {},
): ComparisonResult[] {
  const normalized = normalizeOrderItems(items).items;
  const results = normalized.flatMap((item, index) => {
    const base = Math.max(700, item.targetUnitPrice ?? 1200 + index * 140);
    const unitCount = Math.max(1, item.quantity);
    const platforms: Platform[] = ['coupang', 'naver'];

    return platforms.map((platform, platformIndex) => {
      const shippingFee = platform === 'coupang' && base * unitCount < 19_800 ? 3_000 : platformIndex * 500;
      const listedPrice = Math.round(base * unitCount * (platform === 'coupang' ? 0.94 : 1.02));
      const confidence = confidenceFor(index + platformIndex, platform);
      const calculatedUnitPrice = confidence === 'low'
        ? null
        : Math.round(((listedPrice + shippingFee) / unitCount) * 100) / 100;
      const savingVsTarget = item.targetUnitPrice && calculatedUnitPrice !== null
        ? Math.max(0, Math.round((item.targetUnitPrice - calculatedUnitPrice) * unitCount))
        : undefined;

      return {
        id: `${item.id}-${platform}`,
        orderItemId: item.id,
        productName: item.name,
        platform,
        optionText: `${item.name} ${unitCount}${item.unit} 구성`,
        sellerName: `${platformLabel(platform)} 추천 셀러`,
        listedPrice,
        shippingFee,
        unitCount: confidence === 'low' ? null : unitCount,
        unit: item.unit,
        unitPrice: calculatedUnitPrice,
        unitPriceConfidence: confidence,
        productUrl: platform === 'coupang' ? 'https://www.coupang.com/' : 'https://shopping.naver.com/',
        status: index === 2 && platform === 'coupang' ? 'blocked' : 'ok',
        capturedAt: new Date().toISOString(),
        savingVsTarget,
        backendOrderId: backendOrderIds[item.id],
        syncStatus: backendOrderIds[item.id] ? 'local' : 'local',
      } satisfies ComparisonResult;
    });
  });

  return sortResultsByInputOrder(results, normalized);
}

export function sortResultsByInputOrder(
  results: ComparisonResult[],
  items: Pick<OrderItem, 'id'>[],
): ComparisonResult[] {
  const order = new Map(items.map((item, index) => [item.id, index]));
  return [...results].sort((a, b) => {
    const groupDelta = (order.get(a.orderItemId) ?? Number.MAX_SAFE_INTEGER)
      - (order.get(b.orderItemId) ?? Number.MAX_SAFE_INTEGER);
    if (groupDelta !== 0) return groupDelta;
    if (a.unitPrice === null && b.unitPrice === null) return a.platform.localeCompare(b.platform);
    if (a.unitPrice === null) return 1;
    if (b.unitPrice === null) return -1;
    return a.unitPrice - b.unitPrice;
  });
}

export function initialProgress(): ProcurementProgress {
  return {
    current: 0,
    total: 0,
    percent: 0,
    platforms: [
      { platform: 'coupang', status: 'idle', label: '쿠팡' },
      { platform: 'naver', status: 'idle', label: '네이버' },
    ],
  };
}

export function runningProgress(total: number, percent: number): ProcurementProgress {
  const current = Math.min(total, Math.max(0, Math.round((total * percent) / 100)));
  return {
    current,
    total,
    percent,
    platforms: [
      { platform: 'coupang', status: percent >= 80 ? 'ok' : 'running', label: '쿠팡' },
      { platform: 'naver', status: percent >= 55 ? 'ok' : 'running', label: '네이버' },
    ],
  };
}

export function completeProgress(total: number): ProcurementProgress {
  return {
    current: total,
    total,
    percent: total === 0 ? 0 : 100,
    platforms: [
      { platform: 'coupang', status: 'ok', label: '쿠팡' },
      { platform: 'naver', status: 'ok', label: '네이버' },
    ],
  };
}

export function statusMeta(status: WorkflowStatus): { label: string; tone: string; helper: string } {
  switch (status) {
    case 'ok':
      return { label: '정상', tone: 'success', helper: '정상 처리되었습니다.' };
    case 'running':
      return { label: '조회 중', tone: 'info', helper: '현재 가격 정보를 조회하고 있습니다.' };
    case 'queued':
      return { label: '대기열', tone: 'neutral', helper: '동시 조회 제한으로 잠시 대기 중입니다.' };
    case 'blocked':
      return { label: '차단', tone: 'danger', helper: '플랫폼 봇 탐지로 일시 차단되었습니다.' };
    case 'timeout':
      return { label: '시간 초과', tone: 'warning', helper: '응답 시간이 길어 조회를 멈췄습니다.' };
    case 'login-required':
      return { label: '로그인 필요', tone: 'warning', helper: '앱 WebView에서 직접 로그인 후 다시 시도하세요.' };
    case 'error':
      return { label: '오류', tone: 'danger', helper: '예상하지 못한 오류가 발생했습니다.' };
    case 'idle':
      return { label: '대기', tone: 'neutral', helper: '아직 실행 전입니다.' };
  }
}

export function calculateReportMetrics(results: ComparisonResult[]): {
  metrics: ReportMetric[];
  monthly: MonthlySaving[];
} {
  const completed = results.filter((result) => result.status === 'ok');
  const totalSavings = completed.reduce((sum, result) => sum + (result.savingVsTarget ?? 0), 0);
  const measurable = completed.filter((result) => result.unitPrice !== null).length;
  const bestAverage = measurable
    ? completed.reduce((sum, result) => sum + (result.unitPrice ?? 0), 0) / measurable
    : 0;
  const platformSavings = completed.reduce<Record<Platform, number>>((acc, result) => {
    acc[result.platform] += result.savingVsTarget ?? 0;
    return acc;
  }, { coupang: 0, naver: 0, manual: 0 });
  const topPlatform = Object.entries(platformSavings).sort((a, b) => b[1] - a[1])[0]?.[0] as Platform | undefined;

  return {
    metrics: [
      { label: '예상 절감액', value: formatKrw(totalSavings), helper: '목표 단가 대비 추정' },
      { label: '비교 완료 옵션', value: `${completed.length}개`, helper: '정상 처리된 결과' },
      { label: '평균 최저 실가', value: formatKrw(bestAverage), helper: '계산 가능한 옵션 기준' },
      { label: '강한 플랫폼', value: topPlatform ? platformLabel(topPlatform) : '-', helper: '절감액 기여도 기준' },
    ],
    monthly: [
      { month: '1월', saved: Math.round(totalSavings * 0.34) },
      { month: '2월', saved: Math.round(totalSavings * 0.46) },
      { month: '3월', saved: Math.round(totalSavings * 0.68) },
      { month: '4월', saved: totalSavings },
    ],
  };
}
