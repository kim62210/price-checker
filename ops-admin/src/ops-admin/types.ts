export const viewIds = ['jobs', 'results', 'notifications', 'experiments'] as const;

export type ViewId = (typeof viewIds)[number];
export type SourceId = 'naver' | 'coupang' | 'manual' | 'dual';
export type JobStatus = 'running' | 'retry-scheduled' | 'failed' | 'partial' | 'succeeded' | 'queued';
export type NotificationStatus = 'sending' | 'delivered' | 'fallback' | 'dead-lettered';
export type ExperimentType = 'uploads' | 'parse-runs' | 'compare' | 'regressions';
export type DrawerTone = 'info' | 'success' | 'warning' | 'danger' | 'neutral';

export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

export interface LocalizedText {
  ko: string;
  en: string;
}

export type DisplayText = string | LocalizedText;

export function isLocalizedText(value: DisplayText): value is LocalizedText {
  return typeof value === 'object' && value !== null && 'ko' in value && 'en' in value;
}

export interface TimelineEntry {
  id: string;
  title: DisplayText;
  detail: DisplayText;
  timestamp: string;
  tone: DrawerTone;
}

export interface JobDetail {
  targetUnitPrice: number | null;
  queueDepth: number;
  durationSeconds: number | null;
  policy: DisplayText;
  keptResults: number | null;
  totalResults: number | null;
  rawPayload: JsonValue;
  timeline: TimelineEntry[];
}

export interface JobRow {
  id: string;
  orderId: string;
  productName: string;
  shopName: string;
  quantity: number;
  source: Exclude<SourceId, 'manual' | 'dual'>;
  status: JobStatus;
  attempts: number;
  maxAttempts: number;
  queuedAt: string;
  timeScope: '24h' | '7d' | '30d';
  nextRetryAt?: string;
  finishedAt?: string;
  lastErrorCode?: string;
  lastErrorMessage?: DisplayText;
  detail: JobDetail;
}

export interface ResultSibling {
  id: string;
  seller: string;
  mall: string;
  perUnitPrice: number;
  eligible: boolean;
}

export interface ResultDetail {
  targetUnitPrice: number;
  rawPayload: JsonValue;
  siblings: ResultSibling[];
  validatorNotes: DisplayText[];
  notificationId: string | null;
}

export interface ResultRow {
  id: string;
  orderId: string;
  jobId: string;
  productName: string;
  mallName: string;
  sellerCode: string;
  source: Exclude<SourceId, 'dual'>;
  method: 'shopping_api' | 'parser_upload' | 'manual_review';
  perUnitPrice: number;
  listedPrice: number;
  shippingFee: number;
  compareEligible: boolean;
  partialReason?: string;
  collectedAt: string;
  timeScope: '24h' | '7d' | '30d';
  savingsRate: number | null;
  unitCount: number;
  unitLabel: string;
  isBest: boolean;
  detail: ResultDetail;
}

export interface ProviderAttempt {
  id: string;
  channel: 'alimtalk' | 'sms' | 'lms' | 'brand';
  status: NotificationStatus;
  provider: string;
  timestamp: string;
  detail: DisplayText;
}

export interface NotificationDetail {
  timeline: TimelineEntry[];
  renderedVariables: JsonValue;
  providerAttempts: ProviderAttempt[];
}

export interface NotificationRow {
  id: string;
  eventCode: string;
  orderId: string;
  jobId: string;
  resultId: string | null;
  outboxId: string;
  channel: ProviderAttempt['channel'];
  templateName: string;
  templateVersion: string;
  recipientName: string;
  recipientId: string;
  recipientPhone: string;
  status: NotificationStatus;
  sentAt: string;
  timeScope: '24h' | '7d' | '30d';
  fallbackFrom: ProviderAttempt['channel'] | null;
  detail: NotificationDetail;
}

export interface ExperimentComparisonMetric {
  id: string;
  label: DisplayText;
  leftValue: DisplayText;
  rightValue: DisplayText;
  delta: DisplayText;
}

export interface ExperimentDetail {
  isolatedSchemas: string[];
  excludedPipelines: string[];
  retention: DisplayText;
  rawPayload: JsonValue;
  notes: DisplayText[];
  comparisonMetrics: ExperimentComparisonMetric[];
}

export interface ExperimentRow {
  id: string;
  type: ExperimentType;
  name: string;
  source: SourceId;
  uploader: string;
  parserVersion: string;
  itemCount: number;
  acceptedCount: number;
  compareSummary: string;
  uploadedAt: string;
  detail: ExperimentDetail;
}
