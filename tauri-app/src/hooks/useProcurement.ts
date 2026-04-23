import { useMemo, useReducer } from 'react';
import { createOrder, fetchSummaryReport, uploadResult } from '../api/procurement';
import type { ApiClientOptions } from '../api/client';
import type { SummaryReport } from '../types/api';
import type { ComparisonResult, OrderItem, ProcurementProgress } from '../types/procurement';
import {
  buildMockComparison,
  cloneOrderItems,
  completeProgress,
  createEmptyItem,
  initialProgress,
  normalizeOrderItems,
  parsePastedRows,
  recentOrders,
  runningProgress,
  sortResultsByInputOrder,
} from '../utils/procurement';

interface ProcurementState {
  items: OrderItem[];
  results: ComparisonResult[];
  progress: ProcurementProgress;
  isRunning: boolean;
  notice: string | null;
  apiReport: SummaryReport | null;
  apiMode: 'local-preview' | 'api-connected';
}

interface StartOptions {
  apiOptions: ApiClientOptions;
  shopId: number | null;
  useApi: boolean;
}

type ProcurementAction =
  | { type: 'add-row' }
  | { type: 'remove-row'; id: string }
  | { type: 'update-row'; id: string; patch: Partial<OrderItem> }
  | { type: 'apply-paste'; text: string }
  | { type: 'clone-recent'; recentOrderId: string }
  | { type: 'start'; apiMode: ProcurementState['apiMode'] }
  | { type: 'progress'; progress: ProcurementProgress }
  | { type: 'complete'; results: ComparisonResult[]; apiReport?: SummaryReport | null; notice?: string }
  | { type: 'fail'; notice: string }
  | { type: 'retry-result'; id: string }
  | { type: 'report-loaded'; apiReport: SummaryReport };

const initialState: ProcurementState = {
  items: [
    { id: 'seed-cola', name: '콜라 500ml', quantity: 12, unit: '개', targetUnitPrice: 950 },
    { id: 'seed-water', name: '생수 2L', quantity: 24, unit: '개', targetUnitPrice: 420 },
  ],
  results: [],
  progress: initialProgress(),
  isRunning: false,
  notice: null,
  apiReport: null,
  apiMode: 'local-preview',
};

function reducer(state: ProcurementState, action: ProcurementAction): ProcurementState {
  switch (action.type) {
    case 'add-row':
      return {
        ...state,
        items: [...state.items, createEmptyItem(state.items.length + 1)].slice(0, 50),
        notice: state.items.length >= 50 ? '한 번에 최대 50개까지 비교할 수 있습니다.' : null,
      };
    case 'remove-row':
      return { ...state, items: state.items.filter((item) => item.id !== action.id) };
    case 'update-row':
      return {
        ...state,
        items: state.items.map((item) => (item.id === action.id ? { ...item, ...action.patch } : item)),
      };
    case 'apply-paste': {
      const parsed = parsePastedRows(action.text);
      return {
        ...state,
        items: parsed.items.length ? parsed.items : state.items,
        notice: parsed.truncated
          ? '한 번에 최대 50개까지 비교할 수 있습니다. 51번째 이후 행은 제외했습니다.'
          : null,
      };
    }
    case 'clone-recent': {
      const recent = recentOrders.find((order) => order.id === action.recentOrderId);
      if (!recent) return state;
      return { ...state, items: cloneOrderItems(recent.items, action.recentOrderId), notice: null };
    }
    case 'start': {
      const normalized = normalizeOrderItems(state.items);
      return {
        ...state,
        items: normalized.items,
        isRunning: normalized.items.length > 0,
        progress: normalized.items.length > 0 ? runningProgress(normalized.items.length, 18) : initialProgress(),
        apiMode: action.apiMode,
        notice: normalized.items.length === 0
          ? '최소 1개 품목을 입력해 주세요.'
          : normalized.truncated
            ? '최대 50개 품목만 비교합니다.'
            : action.apiMode === 'api-connected'
              ? 'API에 발주를 생성하고 결과 업로드를 준비합니다.'
              : 'API 미연결 상태입니다. 로컬 미리보기 결과로 비교합니다.',
      };
    }
    case 'progress':
      return { ...state, progress: action.progress };
    case 'complete':
      return {
        ...state,
        results: sortResultsByInputOrder(action.results, state.items),
        progress: completeProgress(state.items.length),
        isRunning: false,
        apiReport: action.apiReport ?? state.apiReport,
        notice: action.notice ?? '비교가 완료되었습니다. 결과표에서 최저 실가를 확인하세요.',
      };
    case 'fail':
      return { ...state, isRunning: false, notice: action.notice };
    case 'retry-result':
      return {
        ...state,
        results: state.results.map((result) => (
          result.id === action.id
            ? { ...result, status: 'ok', unitPriceConfidence: 'medium', syncStatus: result.backendResultId ? 'uploaded' : result.syncStatus }
            : result
        )),
        notice: '선택한 결과를 재시도 처리했습니다.',
      };
    case 'report-loaded':
      return { ...state, apiReport: action.apiReport };
  }
}

function toOrderPayload(item: OrderItem, shopId: number) {
  return {
    shop_id: shopId,
    product_name: item.name,
    option_text: item.memo || null,
    quantity: item.quantity,
    unit: item.unit,
    target_unit_price: item.targetUnitPrice ?? null,
    memo: item.memo ?? null,
    status: 'collecting' as const,
  };
}

function toUploadPayload(result: ComparisonResult) {
  if (result.unitPrice === null || result.unitCount === null) return null;
  return {
    source: result.platform,
    product_url: result.productUrl,
    seller_name: result.sellerName,
    listed_price: result.listedPrice,
    per_unit_price: result.unitPrice,
    shipping_fee: result.shippingFee,
    unit_count: result.unitCount,
    collected_at: result.capturedAt,
  };
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '알 수 없는 API 오류';
}

export function useProcurement() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const canStart = useMemo(
    () => normalizeOrderItems(state.items).items.length > 0 && !state.isRunning,
    [state.items, state.isRunning],
  );

  const runLocalPreview = (normalized: OrderItem[]) => {
    window.setTimeout(() => {
      dispatch({ type: 'progress', progress: runningProgress(normalized.length, 52) });
    }, 250);
    window.setTimeout(() => {
      dispatch({ type: 'progress', progress: runningProgress(normalized.length, 84) });
    }, 550);
    window.setTimeout(() => {
      dispatch({
        type: 'complete',
        results: buildMockComparison(normalized),
        notice: 'API 미연결 로컬 미리보기로 비교가 완료되었습니다. 설정에서 API를 연결하면 발주와 결과가 저장됩니다.',
      });
    }, 850);
  };

  const runApiFlow = async (normalized: OrderItem[], options: StartOptions) => {
    if (!options.shopId) {
      dispatch({ type: 'fail', notice: 'API 연결은 되었지만 선택된 매장이 없습니다. 설정에서 매장을 선택하거나 생성하세요.' });
      return;
    }

    const orderIds: Partial<Record<string, number>> = {};
    const failedItemIds = new Set<string>();

    for (const [index, item] of normalized.entries()) {
      try {
        const order = await createOrder(toOrderPayload(item, options.shopId), options.apiOptions);
        orderIds[item.id] = order.id;
      } catch (error) {
        failedItemIds.add(item.id);
        console.warn(`failed to create order for ${item.name}`, error);
      }
      dispatch({ type: 'progress', progress: runningProgress(normalized.length, 25 + ((index + 1) / normalized.length) * 35) });
    }

    const generated = buildMockComparison(normalized, orderIds).map((result) => (
      failedItemIds.has(result.orderItemId)
        ? { ...result, status: 'error' as const, syncStatus: 'failed' as const, syncError: '발주 생성 실패' }
        : result
    ));

    const uploaded: ComparisonResult[] = [];
    for (const [index, result] of generated.entries()) {
      const payload = toUploadPayload(result);
      if (!payload || !result.backendOrderId || result.status !== 'ok') {
        uploaded.push({
          ...result,
          syncStatus: result.syncStatus ?? 'local',
          syncError: result.status !== 'ok' ? '플랫폼 조회 실패 결과는 업로드하지 않았습니다.' : '수량/단가 산출 실패로 업로드하지 않았습니다.',
        });
        continue;
      }
      try {
        const apiResult = await uploadResult(result.backendOrderId, payload, options.apiOptions);
        uploaded.push({ ...result, backendResultId: apiResult.id, syncStatus: 'uploaded' });
      } catch (error) {
        uploaded.push({ ...result, syncStatus: 'failed', syncError: errorMessage(error) });
      }
      dispatch({ type: 'progress', progress: runningProgress(normalized.length, 60 + ((index + 1) / generated.length) * 32) });
    }

    let apiReport: SummaryReport | null = null;
    try {
      apiReport = await fetchSummaryReport(options.apiOptions);
    } catch (error) {
      console.warn('failed to fetch summary report', error);
    }

    const uploadedCount = uploaded.filter((result) => result.syncStatus === 'uploaded').length;
    const failedCount = uploaded.filter((result) => result.syncStatus === 'failed').length;
    dispatch({
      type: 'complete',
      results: uploaded,
      apiReport,
      notice: `API 연결 비교 완료: 결과 ${uploadedCount}개 업로드${failedCount ? `, ${failedCount}개는 로컬 보관` : ''}.`,
    });
  };

  const startComparison = async (options: StartOptions) => {
    const normalized = normalizeOrderItems(state.items).items;
    const apiMode: ProcurementState['apiMode'] = options.useApi ? 'api-connected' : 'local-preview';
    dispatch({ type: 'start', apiMode });
    if (normalized.length === 0) return;

    if (!options.useApi) {
      runLocalPreview(normalized);
      return;
    }

    await runApiFlow(normalized, options);
  };

  const refreshReport = async (apiOptions: ApiClientOptions) => {
    const report = await fetchSummaryReport(apiOptions);
    dispatch({ type: 'report-loaded', apiReport: report });
  };

  return {
    state,
    recentOrders,
    canStart,
    addRow: () => dispatch({ type: 'add-row' }),
    removeRow: (id: string) => dispatch({ type: 'remove-row', id }),
    updateRow: (id: string, patch: Partial<OrderItem>) => dispatch({ type: 'update-row', id, patch }),
    applyPaste: (text: string) => dispatch({ type: 'apply-paste', text }),
    cloneRecent: (recentOrderId: string) => dispatch({ type: 'clone-recent', recentOrderId }),
    startComparison,
    refreshReport,
    retryResult: (id: string) => dispatch({ type: 'retry-result', id }),
  };
}
