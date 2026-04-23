import { invoke } from '@tauri-apps/api/core';
import type { OrderItem, Platform, WorkflowStatus, Confidence, ComparisonResult } from '../types/procurement';

interface NativeSearchResult {
  id: string;
  orderItemId: string;
  productName: string;
  platform: Platform;
  optionText: string;
  sellerName: string;
  listedPrice: number;
  shippingFee: number;
  unitCount: number | null;
  unit: string;
  unitPrice: number | null;
  unitPriceConfidence: Confidence;
  productUrl: string;
  status: WorkflowStatus;
  capturedAt: string;
  savingVsTarget?: number | null;
  error?: string | null;
}

function isTauriRuntime(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
}

export async function searchMarketplaceItems(items: OrderItem[]): Promise<ComparisonResult[]> {
  if (!isTauriRuntime()) {
    throw new Error('Tauri runtime에서만 쿠팡/네이버 실제 검색을 실행할 수 있습니다.');
  }

  const results = await invoke<NativeSearchResult[]>('search_marketplace_items', {
    items: items.map((item) => ({
      id: item.id,
      name: item.name,
      quantity: item.quantity,
      unit: item.unit,
      targetUnitPrice: item.targetUnitPrice ?? null,
    })),
  });

  return results.map((result) => ({
    id: result.id,
    orderItemId: result.orderItemId,
    productName: result.productName,
    platform: result.platform,
    optionText: result.optionText,
    sellerName: result.sellerName,
    listedPrice: result.listedPrice,
    shippingFee: result.shippingFee,
    unitCount: result.unitCount,
    unit: result.unit,
    unitPrice: result.unitPrice,
    unitPriceConfidence: result.unitPriceConfidence,
    productUrl: result.productUrl,
    status: result.status,
    capturedAt: result.capturedAt,
    savingVsTarget: result.savingVsTarget ?? undefined,
    syncStatus: 'local',
    syncError: result.error ?? undefined,
  }));
}
