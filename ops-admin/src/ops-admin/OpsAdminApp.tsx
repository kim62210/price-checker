import { useEffect, useMemo, useState } from 'react';

import { fetchCurrentUser, fetchNotificationRecipients, fetchOrderResults, fetchOrders, fetchShops, fetchSummaryReport, fetchTenant } from '../api/procurement';
import { useI18n } from '../i18n';
import { experimentsData, jobsData, notificationsData, operatorProfile, resultsData, viewDescriptions } from './data';
import { AdminDrawer } from './AdminDrawer';
import { ExperimentsView, JobsView, NotificationsView, ResultsView } from './AdminViews';
import type { ExperimentRow, JobRow, NotificationRow, ResultRow, ViewId } from './types';
import type { ApiClientOptions } from '../api/client';
import type { NotificationRecipientRead, OrderRead, ResultRead, SummaryReport } from '../types/api';

const apiConfigStorageKey = 'lowest-price.ops-admin.api-config';

function parseHashView(hash: string): ViewId {
  const normalized = hash.replace(/^#\/?/, '');
  if (normalized === 'results' || normalized === 'notifications' || normalized === 'experiments') {
    return normalized;
  }
  return 'jobs';
}

function useHashView(): [ViewId, (view: ViewId) => void] {
  const [view, setView] = useState<ViewId>(() => parseHashView(window.location.hash));

  useEffect(() => {
    const handleHashChange = () => setView(parseHashView(window.location.hash));
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const updateView = (nextView: ViewId) => {
    window.location.hash = `/${nextView}`;
    setView(nextView);
  };

  return [view, updateView];
}

function includesQuery(query: string, parts: Array<string | null | undefined>): boolean {
  if (!query) {
    return true;
  }
  const normalizedQuery = query.trim().toLowerCase();
  return parts.some((part) => part?.toLowerCase().includes(normalizedQuery));
}

interface StoredApiConfig {
  backendUrl: string;
  accessToken: string;
}

interface LiveAdminData {
  jobs: JobRow[];
  results: ResultRow[];
  notifications: NotificationRow[];
  summary: SummaryReport | null;
  ordersCount: number;
  recipientsCount: number;
}

function readStoredApiConfig(): StoredApiConfig {
  if (typeof window === 'undefined') {
    return { backendUrl: 'http://localhost:8000', accessToken: '' };
  }

  const raw = window.localStorage.getItem(apiConfigStorageKey);
  if (!raw) {
    return { backendUrl: 'http://localhost:8000', accessToken: '' };
  }

  try {
    const parsed = JSON.parse(raw) as Partial<StoredApiConfig>;
    return {
      backendUrl: typeof parsed.backendUrl === 'string' ? parsed.backendUrl : 'http://localhost:8000',
      accessToken: typeof parsed.accessToken === 'string' ? parsed.accessToken : '',
    };
  } catch (error) {
    return { backendUrl: 'http://localhost:8000', accessToken: '' };
  }
}

function decimalToNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined) {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function orderToJob(row: OrderRead): JobRow {
  const statusMap: Record<OrderRead['status'], JobRow['status']> = {
    draft: 'queued',
    collecting: 'running',
    completed: 'succeeded',
    cancelled: 'failed',
  };
  const targetUnitPrice = decimalToNumber(row.target_unit_price);

  return {
    id: `order-${row.id}`,
    orderId: `order#${row.id}`,
    productName: row.option_text ? `${row.product_name} · ${row.option_text}` : row.product_name,
    shopName: `shop#${row.shop_id}`,
    quantity: row.quantity,
    source: 'naver',
    status: statusMap[row.status],
    attempts: row.status === 'draft' ? 0 : 1,
    maxAttempts: 3,
    queuedAt: row.created_at,
    finishedAt: row.status === 'completed' || row.status === 'cancelled' ? row.updated_at : undefined,
    timeScope: '24h',
    detail: {
      targetUnitPrice,
      queueDepth: row.status === 'draft' ? 1 : 0,
      durationSeconds: null,
      policy: { ko: '백엔드 procurement 주문 상태 기반', en: 'Derived from backend procurement order status' },
      keptResults: null,
      totalResults: null,
      rawPayload: {
        source: 'backend_api',
        orderId: row.id,
        status: row.status,
        memo: row.memo,
      },
      timeline: [
        { id: `order-${row.id}-created`, title: { ko: '백엔드 주문 생성', en: 'Backend order created' }, detail: '/api/v1/procurement/orders', timestamp: row.created_at, tone: 'info' },
        { id: `order-${row.id}-updated`, title: { ko: '상태 갱신', en: 'Status updated' }, detail: row.status, timestamp: row.updated_at, tone: row.status === 'completed' ? 'success' : 'neutral' },
      ],
    },
  };
}

function resultToRow(row: ResultRead, order?: OrderRead): ResultRow {
  const perUnitPrice = decimalToNumber(row.per_unit_price) ?? 0;
  const listedPrice = decimalToNumber(row.listed_price) ?? 0;
  const shippingFee = decimalToNumber(row.shipping_fee) ?? 0;
  const targetUnitPrice = decimalToNumber(order?.target_unit_price) ?? perUnitPrice;
  const productName = order?.option_text ? `${order.product_name} · ${order.option_text}` : order?.product_name ?? `order#${row.order_id}`;

  return {
    id: `result-${row.id}`,
    orderId: `order#${row.order_id}`,
    jobId: `order-${row.order_id}`,
    productName,
    mallName: row.seller_name ?? row.source,
    sellerCode: row.product_url,
    source: row.source,
    method: row.source === 'manual' ? 'manual_review' : row.source === 'coupang' ? 'parser_upload' : 'shopping_api',
    perUnitPrice,
    listedPrice,
    shippingFee,
    compareEligible: true,
    collectedAt: row.collected_at,
    timeScope: '24h',
    savingsRate: targetUnitPrice > 0 ? ((targetUnitPrice - perUnitPrice) / targetUnitPrice) * 100 : null,
    unitCount: row.unit_count,
    unitLabel: '개',
    isBest: false,
    detail: {
      targetUnitPrice,
      rawPayload: {
        source: 'backend_api',
        resultId: row.id,
        productUrl: row.product_url,
      },
      siblings: [],
      validatorNotes: [{ ko: '백엔드 결과에서 동기화됨', en: 'Synced from backend result' }],
      notificationId: null,
    },
  };
}

function recipientToNotification(row: NotificationRecipientRead): NotificationRow {
  const status: NotificationRow['status'] = row.is_active ? 'delivered' : 'dead-lettered';
  return {
    id: `recipient-${row.id}`,
    eventCode: row.is_active ? 'notification.recipient.active' : 'notification.recipient.inactive',
    orderId: 'recipient-admin',
    jobId: 'notification-recipient-sync',
    resultId: null,
    outboxId: `recipient#${row.id}`,
    channel: 'alimtalk',
    templateName: 'recipient_management',
    templateVersion: 'api',
    recipientName: row.display_name,
    recipientId: `recipient#${row.id}`,
    recipientPhone: row.phone_e164,
    status,
    sentAt: row.updated_at,
    timeScope: '24h',
    fallbackFrom: null,
    detail: {
      timeline: [
        { id: `recipient-${row.id}-created`, title: { ko: '수신자 생성', en: 'Recipient created' }, detail: '/api/v1/notifications/recipients', timestamp: row.created_at, tone: 'info' },
        { id: `recipient-${row.id}-updated`, title: { ko: '수신자 상태 동기화', en: 'Recipient status synced' }, detail: row.is_active ? 'active' : 'inactive', timestamp: row.updated_at, tone: row.is_active ? 'success' : 'danger' },
      ],
      renderedVariables: {
        source: 'backend_api',
        recipient_id: row.id,
        shop_id: row.shop_id,
        user_id: row.user_id,
      },
      providerAttempts: [],
    },
  };
}

async function fetchLiveAdminData(options: ApiClientOptions): Promise<LiveAdminData> {
  const [orders, recipients, summary] = await Promise.all([
    fetchOrders(options),
    fetchNotificationRecipients(options),
    fetchSummaryReport(options).catch(() => null),
  ]);

  const resultLists = await Promise.all(
    orders.slice(0, 8).map((order) => fetchOrderResults(order.id, options).catch(() => [])),
  );
  const results = resultLists.flat().map((result) => resultToRow(result, orders.find((order) => order.id === result.order_id)));

  return {
    jobs: orders.map(orderToJob),
    results,
    notifications: recipients.map(recipientToNotification),
    summary,
    ordersCount: orders.length,
    recipientsCount: recipients.length,
  };
}

export function OpsAdminApp() {
  const { locale, setLocale, t, formatCompactNumber, formatDateTime } = useI18n();
  const [view, setView] = useHashView();
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [apiConfig, setApiConfig] = useState<StoredApiConfig>(readStoredApiConfig);
  const [backendUrlInput, setBackendUrlInput] = useState(apiConfig.backendUrl);
  const [accessTokenInput, setAccessTokenInput] = useState(apiConfig.accessToken);
  const [liveData, setLiveData] = useState<LiveAdminData | null>(null);
  const [apiStatus, setApiStatus] = useState<'idle' | 'syncing' | 'connected' | 'error'>('idle');
  const [apiError, setApiError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [jobsTab, setJobsTab] = useState<'all' | 'running' | 'retry' | 'failed' | 'succeeded'>('all');
  const [jobsSource, setJobsSource] = useState<'all' | 'naver' | 'coupang'>('all');
  const [jobsShop, setJobsShop] = useState<'all' | string>('all');
  const [jobsRange, setJobsRange] = useState<'24h' | '7d' | '30d'>('24h');
  const [resultsTab, setResultsTab] = useState<'all' | 'eligible' | 'rejected' | 'best'>('all');
  const [resultsSource, setResultsSource] = useState<'all' | 'naver' | 'coupang' | 'manual'>('all');
  const [resultsMethod, setResultsMethod] = useState<'all' | 'shopping_api' | 'parser_upload' | 'manual_review'>('all');
  const [resultsRange, setResultsRange] = useState<'24h' | '7d' | '30d'>('24h');
  const [notificationsTab, setNotificationsTab] = useState<'all' | 'inflight' | 'delivered' | 'fallback' | 'failed'>('all');
  const [notificationsChannel, setNotificationsChannel] = useState<'all' | 'alimtalk' | 'sms' | 'lms'>('all');
  const [notificationsRange, setNotificationsRange] = useState<'24h' | '7d' | '30d'>('24h');
  const [experimentsTab, setExperimentsTab] = useState<'uploads' | 'parse-runs' | 'compare' | 'regressions'>('uploads');
  const [experimentsParser, setExperimentsParser] = useState<'all' | 'current'>('all');
  const [now, setNow] = useState(() => new Date());

  const effectiveJobs = liveData ? liveData.jobs : jobsData;
  const effectiveResults = liveData ? liveData.results : resultsData;
  const effectiveNotifications = liveData ? liveData.notifications : notificationsData;

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    setSelectedId(null);
  }, [view]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(apiConfigStorageKey, JSON.stringify(apiConfig));
    }
  }, [apiConfig]);

  const syncLiveData = async () => {
    const nextConfig = { backendUrl: backendUrlInput.trim() || 'http://localhost:8000', accessToken: accessTokenInput.trim() };
    setApiConfig(nextConfig);
    setApiStatus('syncing');
    setApiError(null);
    setActionNotice(null);

    try {
      const options: ApiClientOptions = { baseUrl: nextConfig.backendUrl, accessToken: nextConfig.accessToken || null };
      await Promise.all([fetchTenant(options), fetchCurrentUser(options), fetchShops(options)]);
      const data = await fetchLiveAdminData(options);
      setLiveData(data);
      setApiStatus('connected');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'unknown_error';
      setApiError(message);
      setApiStatus('error');
    }
  };

  const saveApiConfig = () => {
    setApiConfig({ backendUrl: backendUrlInput.trim() || 'http://localhost:8000', accessToken: accessTokenInput.trim() });
  };

  const announceUnavailableAction = (action: string) => {
    setActionNotice(t('app.actionUnavailable', { action }));
  };

  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setSelectedId(null);
      }
    };

    if (selectedId) {
      window.addEventListener('keydown', handleEscape);
      return () => window.removeEventListener('keydown', handleEscape);
    }

    return undefined;
  }, [selectedId]);

  const filteredJobs = useMemo(() => effectiveJobs.filter((row) => {
    if (jobsRange !== row.timeScope && jobsRange !== '30d') return false;
    if (jobsSource !== 'all' && row.source !== jobsSource) return false;
    if (jobsShop !== 'all' && row.shopName !== jobsShop) return false;
    if (jobsTab === 'running' && row.status !== 'running') return false;
    if (jobsTab === 'retry' && row.status !== 'retry-scheduled') return false;
    if (jobsTab === 'failed' && row.status !== 'failed') return false;
    if (jobsTab === 'succeeded' && row.status !== 'succeeded') return false;
    return includesQuery(search, [row.id, row.orderId, row.productName, row.shopName, row.lastErrorCode]);
  }), [effectiveJobs, jobsRange, jobsShop, jobsSource, jobsTab, search]);

  const filteredResults = useMemo(() => effectiveResults.filter((row) => {
    if (resultsRange !== row.timeScope && resultsRange !== '30d') return false;
    if (resultsSource !== 'all' && row.source !== resultsSource) return false;
    if (resultsMethod !== 'all' && row.method !== resultsMethod) return false;
    if (resultsTab === 'eligible' && !row.compareEligible) return false;
    if (resultsTab === 'rejected' && row.compareEligible) return false;
    if (resultsTab === 'best' && !row.isBest) return false;
    return includesQuery(search, [row.id, row.orderId, row.jobId, row.productName, row.mallName, row.partialReason]);
  }), [effectiveResults, resultsMethod, resultsRange, resultsSource, resultsTab, search]);

  const filteredNotifications = useMemo(() => effectiveNotifications.filter((row) => {
    if (notificationsRange !== row.timeScope && notificationsRange !== '30d') return false;
    if (notificationsChannel !== 'all' && row.channel !== notificationsChannel) return false;
    if (notificationsTab === 'inflight' && row.status !== 'sending') return false;
    if (notificationsTab === 'delivered' && row.status !== 'delivered') return false;
    if (notificationsTab === 'fallback' && row.status !== 'fallback') return false;
    if (notificationsTab === 'failed' && row.status !== 'dead-lettered') return false;
    return includesQuery(search, [row.id, row.orderId, row.jobId, row.recipientName, row.recipientId, row.eventCode]);
  }), [effectiveNotifications, notificationsChannel, notificationsRange, notificationsTab, search]);

  const filteredExperiments = useMemo(() => experimentsData.filter((row) => {
    if (experimentsTab !== row.type) return false;
    if (experimentsParser === 'current' && !row.parserVersion.includes('v0.4.0')) return false;
    return includesQuery(search, [row.id, row.name, row.uploader, row.parserVersion, row.compareSummary]);
  }), [experimentsParser, experimentsTab, search]);

  const selectedEntity = useMemo<JobRow | ResultRow | NotificationRow | ExperimentRow | null>(() => {
    if (!selectedId) {
      return null;
    }

    if (view === 'jobs') return filteredJobs.find((row) => row.id === selectedId) ?? null;
    if (view === 'results') return filteredResults.find((row) => row.id === selectedId) ?? null;
    if (view === 'notifications') return filteredNotifications.find((row) => row.id === selectedId) ?? null;
    return filteredExperiments.find((row) => row.id === selectedId) ?? null;
  }, [filteredExperiments, filteredJobs, filteredNotifications, filteredResults, selectedId, view]);

  useEffect(() => {
    if (selectedId && !selectedEntity) {
      setSelectedId(null);
    }
  }, [selectedEntity, selectedId]);

  const viewMeta = viewDescriptions[view];
  const drawer = selectedEntity ? <AdminDrawer view={view} entity={selectedEntity} onClose={() => setSelectedId(null)} /> : null;

  return (
    <div className="ops-shell">
      <aside className="ops-sidebar">
        <div className="brand-block">
          <div className="brand-mark">D</div>
          <div>
            <strong>{t('app.brand')}</strong>
            <small>{t('app.tagline')}</small>
          </div>
        </div>

        <nav aria-label={t('aria.sidebar')} className="sidebar-nav">
          <div className="sidebar-group">
            <div className="sidebar-group-label">{t('nav.group.operations')}</div>
            {(['jobs', 'results', 'notifications'] as const).map((item) => (
              <button key={item} type="button" className={`sidebar-link ${view === item ? 'is-active' : ''}`} onClick={() => setView(item)}>
                <span>{t(`nav.${item}` as const)}</span>
                <span className="sidebar-badge">{formatCompactNumber(item === 'jobs' ? jobsData.length : item === 'results' ? resultsData.length : notificationsData.length)}</span>
              </button>
            ))}
          </div>
          <div className="sidebar-group">
            <div className="sidebar-group-label">{t('nav.group.internal')}</div>
            <button type="button" className={`sidebar-link ${view === 'experiments' ? 'is-active' : ''}`} onClick={() => setView('experiments')}>
              <span>{t('nav.experiments')}</span>
              <span className="sidebar-badge">{formatCompactNumber(experimentsData.length)}</span>
            </button>
          </div>
        </nav>

        <div className="sidebar-footer">
          <div className="operator-block">
            <div className="operator-avatar">HK</div>
            <div>
              <strong>{operatorProfile.name}</strong>
              <small>{operatorProfile.tenant}</small>
            </div>
          </div>
          <span className="env-pill">{operatorProfile.environment}</span>
        </div>
      </aside>

      <div className="ops-main">
        <header className="ops-topbar">
          <div className="topbar-heading">
            <div className="topbar-breadcrumb">{t('app.brand')} / {t(`nav.${view}` as const)}</div>
            <h1>{t(`nav.${view}` as const)}</h1>
            <p><span className="eyebrow-chip">{viewMeta.eyebrow}</span>{t(viewMeta.descriptionKey)}</p>
          </div>

          <div className="topbar-tools">
            <label className="search-field">
              <span className="sr-only">{t('app.searchAria')}</span>
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t('app.searchPlaceholder')} aria-label={t('app.searchAria')} />
              <span className="search-hint">{t('app.commandHint')}</span>
            </label>
            <div className="topbar-meta">
              <span className="meta-chip"><strong>{t('label.currentShop')}</strong>{operatorProfile.currentShop}</span>
              <span className="meta-chip"><strong>{t('label.environment')}</strong>{operatorProfile.environment}</span>
              <span className="meta-chip"><strong>{apiStatus === 'connected' ? t('app.dataSource.live') : t('app.dataSource.sample')}</strong>{apiStatus === 'syncing' ? t('app.syncing') : apiStatus === 'error' ? t('app.status.error') : liveData?.summary ? formatCompactNumber(liveData.summary.results_count) : formatCompactNumber(effectiveResults.length)}</span>
              <span className="meta-chip"><strong>{t('label.live')}</strong>{formatDateTime(now, { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
            </div>
            <div className="api-sync-panel">
              <label>
                <span>{t('app.backendUrl')}</span>
                <input value={backendUrlInput} onChange={(event) => setBackendUrlInput(event.target.value)} />
              </label>
              <label>
                <span>{t('app.accessToken')}</span>
                <input value={accessTokenInput} onChange={(event) => setAccessTokenInput(event.target.value)} type="password" />
              </label>
              <button type="button" className="primary-action" onClick={() => void syncLiveData()} disabled={apiStatus === 'syncing'}>{apiStatus === 'syncing' ? t('app.syncing') : t('app.syncLive')}</button>
              <button type="button" className="ghost-link" onClick={saveApiConfig}>{t('app.saveConfig')}</button>
            </div>
            <p className={`api-sync-status ${apiStatus === 'error' ? 'is-error' : ''}`}>
              {apiStatus === 'connected' && liveData ? t('app.apiConnected', { orders: liveData.ordersCount, recipients: liveData.recipientsCount }) : apiError ? t('app.apiError', { message: apiError }) : t('app.apiFallback')}
            </p>
            <div className="language-switcher" aria-label={t('aria.languageSwitcher')}>
              <button type="button" className={locale === 'ko' ? 'is-active' : ''} onClick={() => setLocale('ko')}>{t('common.language.ko')}</button>
              <button type="button" className={locale === 'en' ? 'is-active' : ''} onClick={() => setLocale('en')}>{t('common.language.en')}</button>
            </div>
          </div>
        </header>

        <main className="ops-content">
          {view === 'jobs' ? (
            <JobsView
              rows={filteredJobs}
              allRows={effectiveJobs}
              selectedId={selectedId}
              activeTab={jobsTab}
              sourceFilter={jobsSource}
              shopFilter={jobsShop}
              rangeFilter={jobsRange}
              onTabChange={setJobsTab}
              onSourceChange={setJobsSource}
              onShopChange={setJobsShop}
              onRangeChange={setJobsRange}
              onSelect={setSelectedId}
              onAction={announceUnavailableAction}
              actionNotice={actionNotice}
              drawer={drawer}
            />
          ) : null}

          {view === 'results' ? (
            <ResultsView
              rows={filteredResults}
              allRows={effectiveResults}
              selectedId={selectedId}
              activeTab={resultsTab}
              sourceFilter={resultsSource}
              methodFilter={resultsMethod}
              rangeFilter={resultsRange}
              onTabChange={setResultsTab}
              onSourceChange={setResultsSource}
              onMethodChange={setResultsMethod}
              onRangeChange={setResultsRange}
              onSelect={setSelectedId}
              onAction={announceUnavailableAction}
              actionNotice={actionNotice}
              drawer={drawer}
            />
          ) : null}

          {view === 'notifications' ? (
            <NotificationsView
              rows={filteredNotifications}
              allRows={effectiveNotifications}
              selectedId={selectedId}
              activeTab={notificationsTab}
              channelFilter={notificationsChannel}
              rangeFilter={notificationsRange}
              onTabChange={setNotificationsTab}
              onChannelChange={setNotificationsChannel}
              onRangeChange={setNotificationsRange}
              onSelect={setSelectedId}
              onAction={announceUnavailableAction}
              actionNotice={actionNotice}
              drawer={drawer}
            />
          ) : null}

          {view === 'experiments' ? (
            <ExperimentsView
              rows={filteredExperiments}
              allRows={experimentsData}
              selectedId={selectedId}
              activeTab={experimentsTab}
              parserFilter={experimentsParser}
              onTabChange={setExperimentsTab}
              onParserChange={setExperimentsParser}
              onSelect={setSelectedId}
              onAction={announceUnavailableAction}
              actionNotice={actionNotice}
              drawer={drawer}
            />
          ) : null}
        </main>
      </div>
    </div>
  );
}
