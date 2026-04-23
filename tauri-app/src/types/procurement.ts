export type Platform = 'naver' | 'coupang' | 'manual';

export type WorkflowStatus =
  | 'idle'
  | 'queued'
  | 'running'
  | 'ok'
  | 'blocked'
  | 'timeout'
  | 'login-required'
  | 'error';

export type Confidence = 'high' | 'medium' | 'low';

export interface OrderItem {
  id: string;
  name: string;
  quantity: number;
  unit: string;
  targetUnitPrice?: number;
  memo?: string;
}

export interface RecentOrder {
  id: string;
  label: string;
  createdAt: string;
  items: OrderItem[];
}

export type SyncStatus = 'local' | 'uploaded' | 'failed';

export interface ComparisonResult {
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
  savingVsTarget?: number;
  backendOrderId?: number;
  backendResultId?: number;
  syncStatus?: SyncStatus;
  syncError?: string;
}

export interface PlatformProgress {
  platform: Platform;
  status: WorkflowStatus;
  label: string;
}

export interface ProcurementProgress {
  current: number;
  total: number;
  percent: number;
  platforms: PlatformProgress[];
}

export interface ReportMetric {
  label: string;
  value: string;
  helper: string;
}

export interface MonthlySaving {
  month: string;
  saved: number;
}
