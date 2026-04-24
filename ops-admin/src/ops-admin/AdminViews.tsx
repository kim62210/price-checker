import { useMemo } from 'react';

import type { ReactNode } from 'react';

import { useI18n } from '../i18n';
import { isLocalizedText } from './types';
import type { DisplayText, ExperimentRow, JobRow, NotificationRow, ResultRow } from './types';

interface FilterOption<T extends string> {
  value: T;
  label: string;
}

interface TabDefinition<T extends string> {
  value: T;
  label: string;
  count: number;
}

interface JobsViewProps {
  rows: JobRow[];
  allRows: JobRow[];
  selectedId: string | null;
  activeTab: 'all' | 'running' | 'retry' | 'failed' | 'succeeded';
  sourceFilter: 'all' | 'naver' | 'coupang';
  shopFilter: 'all' | string;
  rangeFilter: '24h' | '7d' | '30d';
  onTabChange: (value: JobsViewProps['activeTab']) => void;
  onSourceChange: (value: JobsViewProps['sourceFilter']) => void;
  onShopChange: (value: JobsViewProps['shopFilter']) => void;
  onRangeChange: (value: JobsViewProps['rangeFilter']) => void;
  onSelect: (id: string) => void;
  onAction: (action: string) => void;
  actionNotice: string | null;
  drawer: ReactNode;
}

interface ResultsViewProps {
  rows: ResultRow[];
  allRows: ResultRow[];
  selectedId: string | null;
  activeTab: 'all' | 'eligible' | 'rejected' | 'best';
  sourceFilter: 'all' | 'naver' | 'coupang' | 'manual';
  methodFilter: 'all' | 'shopping_api' | 'parser_upload' | 'manual_review';
  rangeFilter: '24h' | '7d' | '30d';
  onTabChange: (value: ResultsViewProps['activeTab']) => void;
  onSourceChange: (value: ResultsViewProps['sourceFilter']) => void;
  onMethodChange: (value: ResultsViewProps['methodFilter']) => void;
  onRangeChange: (value: ResultsViewProps['rangeFilter']) => void;
  onSelect: (id: string) => void;
  onAction: (action: string) => void;
  actionNotice: string | null;
  drawer: ReactNode;
}

interface NotificationsViewProps {
  rows: NotificationRow[];
  allRows: NotificationRow[];
  selectedId: string | null;
  activeTab: 'all' | 'inflight' | 'delivered' | 'fallback' | 'failed';
  channelFilter: 'all' | 'alimtalk' | 'sms' | 'lms';
  rangeFilter: '24h' | '7d' | '30d';
  onTabChange: (value: NotificationsViewProps['activeTab']) => void;
  onChannelChange: (value: NotificationsViewProps['channelFilter']) => void;
  onRangeChange: (value: NotificationsViewProps['rangeFilter']) => void;
  onSelect: (id: string) => void;
  onAction: (action: string) => void;
  actionNotice: string | null;
  drawer: ReactNode;
}

interface ExperimentsViewProps {
  rows: ExperimentRow[];
  allRows: ExperimentRow[];
  selectedId: string | null;
  activeTab: 'uploads' | 'parse-runs' | 'compare' | 'regressions';
  parserFilter: 'all' | 'current';
  onTabChange: (value: ExperimentsViewProps['activeTab']) => void;
  onParserChange: (value: ExperimentsViewProps['parserFilter']) => void;
  onSelect: (id: string) => void;
  onAction: (action: string) => void;
  actionNotice: string | null;
  drawer: ReactNode;
}

function tableRowProps(id: string, selectedId: string | null) {
  return {
    className: selectedId === id ? 'is-selected' : '',
  };
}

function localizeText(value: DisplayText, locale: 'ko' | 'en'): string {
  return isLocalizedText(value) ? value[locale] : value;
}

function FilterChip<T extends string>({
  options,
  value,
  onChange,
}: {
  options: FilterOption<T>[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="chip-group">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={`filter-chip ${option.value === value ? 'is-active' : ''}`}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function TabBar<T extends string>({
  tabs,
  value,
  onChange,
  ariaLabel,
  panelId,
}: {
  tabs: TabDefinition<T>[];
  value: T;
  onChange: (value: T) => void;
  ariaLabel: string;
  panelId: string;
}) {
  return (
    <div className="subbar-tabs" role="tablist" aria-label={ariaLabel}>
      {tabs.map((tab) => (
        <button
          key={tab.value}
          type="button"
          role="tab"
          aria-selected={tab.value === value}
          aria-controls={panelId}
          id={`${panelId}-${tab.value}-tab`}
          className={`subbar-tab ${tab.value === value ? 'is-active' : ''}`}
          onClick={() => onChange(tab.value)}
        >
          <span>{tab.label}</span>
          <span className="subbar-count">{tab.count}</span>
        </button>
      ))}
    </div>
  );
}

function OpenDetailsButton({ id, label, onSelect }: { id: string; label: string; onSelect: (id: string) => void; }) {
  return (
    <button
      type="button"
      className="row-open-button"
      onClick={(event) => {
        event.stopPropagation();
        onSelect(id);
      }}
      aria-label={label}
    >
      {id}
    </button>
  );
}

function MetricCard({ label, value, helper, tone = 'neutral' }: { label: string; value: string; helper: string; tone?: 'neutral' | 'amber' | 'info' | 'success' | 'warning' | 'danger'; }) {
  return (
    <article className={`metric-card tone-${tone}`}>
      <span className="metric-label">{label}</span>
      <strong className="metric-value">{value}</strong>
      <small className="metric-helper">{helper}</small>
    </article>
  );
}

function EmptyState() {
  const { t } = useI18n();
  return (
    <div className="empty-state">
      <strong>{t('empty.title')}</strong>
      <p>{t('empty.description')}</p>
    </div>
  );
}

function SourceTag({ source }: { source: 'naver' | 'coupang' | 'manual' | 'dual'; }) {
  return <span className={`source-tag source-${source}`}>{source}</span>;
}

function StatusPill({ label, tone }: { label: string; tone: 'info' | 'warning' | 'danger' | 'success' | 'neutral'; }) {
  return <span className={`status-pill tone-${tone}`}>{label}</span>;
}

function AttemptsDots({ attempts, maxAttempts }: { attempts: number; maxAttempts: number; }) {
  return (
    <span className="attempt-dots" aria-hidden="true">
      {Array.from({ length: maxAttempts }, (_, index) => (
        <span key={index} className={`attempt-dot ${index < attempts ? 'is-filled' : ''}`} />
      ))}
    </span>
  );
}

function FooterSummary({ visible, total }: { visible: number; total: number; }) {
  const { t } = useI18n();
  return <div className="table-footer">{t('common.showingRows', { visible, total })}</div>;
}

function jobTone(status: JobRow['status']): 'info' | 'warning' | 'danger' | 'success' | 'neutral' {
  switch (status) {
    case 'running':
      return 'info';
    case 'retry-scheduled':
    case 'partial':
      return 'warning';
    case 'failed':
      return 'danger';
    case 'succeeded':
      return 'success';
    case 'queued':
      return 'neutral';
  }
}

function notificationTone(status: NotificationRow['status']): 'info' | 'warning' | 'danger' | 'success' | 'neutral' {
  switch (status) {
    case 'sending':
      return 'info';
    case 'fallback':
      return 'warning';
    case 'dead-lettered':
      return 'danger';
    case 'delivered':
      return 'success';
  }
}

export function JobsView({
  rows,
  allRows,
  selectedId,
  activeTab,
  sourceFilter,
  shopFilter,
  rangeFilter,
  onTabChange,
  onSourceChange,
  onShopChange,
  onRangeChange,
  onSelect,
  onAction,
  actionNotice,
  drawer,
}: JobsViewProps) {
  const { locale, t, formatNumber, formatPercent, formatDateTime, formatRelativeTime } = useI18n();

  const tabs = useMemo<TabDefinition<JobsViewProps['activeTab']>[]>(() => [
    { value: 'all', label: t('jobs.tabs.all'), count: allRows.length },
    { value: 'running', label: t('jobs.tabs.running'), count: allRows.filter((row) => row.status === 'running').length },
    { value: 'retry', label: t('jobs.tabs.retry'), count: allRows.filter((row) => row.status === 'retry-scheduled').length },
    { value: 'failed', label: t('jobs.tabs.failed'), count: allRows.filter((row) => row.status === 'failed').length },
    { value: 'succeeded', label: t('jobs.tabs.succeeded'), count: allRows.filter((row) => row.status === 'succeeded').length },
  ], [allRows, t]);

  const shops = Array.from(new Set(allRows.map((row) => row.shopName)));
  const visibleSuccessRate = rows.length ? ((rows.filter((row) => row.status === 'succeeded' || row.status === 'partial').length / rows.length) * 100) : 0;
  const avgDuration = rows.filter((row) => row.detail.durationSeconds !== null).reduce((sum, row) => sum + (row.detail.durationSeconds ?? 0), 0) / Math.max(1, rows.filter((row) => row.detail.durationSeconds !== null).length);

  return (
    <section className="view-shell">
      <div className="view-subbar">
        <TabBar tabs={tabs} value={activeTab} onChange={onTabChange} ariaLabel={t('aria.viewTabs')} panelId="jobs-tabpanel" />
        <div className="subbar-filters" aria-label={t('aria.filterGroup')}>
          <FilterChip
            value={rangeFilter}
            onChange={onRangeChange}
            options={[
              { value: '24h', label: `${t('common.range')} · ${t('common.timeScope.24h')}` },
              { value: '7d', label: `${t('common.range')} · ${t('common.timeScope.7d')}` },
              { value: '30d', label: `${t('common.range')} · ${t('common.timeScope.30d')}` },
            ]}
          />
          <FilterChip
            value={sourceFilter}
            onChange={onSourceChange}
            options={[
              { value: 'all', label: `${t('common.source')} · ${t('common.filter.all')}` },
              { value: 'naver', label: `${t('common.source')} · ${t('common.source.naver')}` },
              { value: 'coupang', label: `${t('common.source')} · ${t('common.source.coupang')}` },
            ]}
          />
          <FilterChip
            value={shopFilter}
            onChange={onShopChange}
            options={[{ value: 'all', label: `${t('common.shop')} · ${t('common.filter.all')}` }, ...shops.map((shop) => ({ value: shop, label: `${t('common.shop')} · ${shop}` }))]}
          />
          <button type="button" className="primary-action" onClick={() => onAction(t('jobs.actions.triggerCollect'))}>{t('jobs.actions.triggerCollect')}</button>
        </div>
      </div>
      {actionNotice ? <p className="action-notice">{actionNotice}</p> : null}

      <div className={`workspace ${drawer ? 'has-drawer' : ''}`}>
        <div className="workspace-main" role="tabpanel" id="jobs-tabpanel" aria-labelledby={`jobs-tabpanel-${activeTab}-tab`}>
          <div className="metric-strip jobs-grid">
            <MetricCard label={t('jobs.kpi.running')} value={formatNumber(rows.filter((row) => row.status === 'running').length)} helper={`${t('jobs.kpi.avgDuration')} ${avgDuration ? `${avgDuration.toFixed(1)}s` : t('common.na')}`} tone="info" />
            <MetricCard label={t('jobs.kpi.retry')} value={formatNumber(rows.filter((row) => row.status === 'retry-scheduled').length)} helper={`${t('jobs.kpi.topReason')} NAVER_RATE_LIMIT`} tone="warning" />
            <MetricCard label={t('jobs.kpi.failures')} value={formatNumber(rows.filter((row) => row.status === 'failed').length)} helper={`${t('jobs.kpi.topReason')} NAVER_NO_RESULT`} tone="danger" />
            <MetricCard label={t('jobs.kpi.successRate')} value={formatPercent(visibleSuccessRate, 1)} helper={`${t('jobs.kpi.slo')} ${t('jobs.kpi.sloValue')}`} tone="amber" />
          </div>

          {rows.length === 0 ? <EmptyState /> : (
            <div className="table-scroll">
              <table className="ops-table">
                <thead>
                  <tr>
                    <th>{t('jobs.table.job')}</th>
                    <th>{t('jobs.table.orderProduct')}</th>
                    <th>{t('jobs.table.status')}</th>
                    <th>{t('jobs.table.source')}</th>
                    <th>{t('jobs.table.attempts')}</th>
                    <th>{t('jobs.table.next')}</th>
                    <th>{t('jobs.table.lastError')}</th>
                    <th>{t('jobs.table.queued')}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} {...tableRowProps(row.id, selectedId)}>
                      <td className="mono-cell"><OpenDetailsButton id={row.id} label={`${t('common.openDetails')} ${row.id}`} onSelect={onSelect} /></td>
                      <td>
                        <div className="table-primary">{row.productName}</div>
                        <div className="table-secondary">{row.orderId} · {row.shopName} · {t('jobs.kpi.qtyLabel')} {row.quantity}</div>
                      </td>
                      <td><StatusPill label={t(`common.jobStatus.${row.status}` as const)} tone={jobTone(row.status)} /></td>
                      <td><SourceTag source={row.source} /></td>
                      <td className="attempts-cell"><AttemptsDots attempts={row.attempts} maxAttempts={row.maxAttempts} /><span>{row.attempts}/{row.maxAttempts}</span></td>
                      <td>{row.nextRetryAt ? `${t('label.retryCountdown')} · ${formatDateTime(row.nextRetryAt)}` : row.finishedAt ? `${t('label.finished')} · ${formatDateTime(row.finishedAt)}` : t('label.inFlight')}</td>
                      <td className="mono-cell">{row.lastErrorCode && row.lastErrorMessage ? `${row.lastErrorCode} · ${localizeText(row.lastErrorMessage, locale)}` : t('common.na')}</td>
                      <td>{formatDateTime(row.queuedAt)} · {formatRelativeTime(row.queuedAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <FooterSummary visible={rows.length} total={allRows.length} />
        </div>
        {drawer}
      </div>
    </section>
  );
}

export function ResultsView({
  rows,
  allRows,
  selectedId,
  activeTab,
  sourceFilter,
  methodFilter,
  rangeFilter,
  onTabChange,
  onSourceChange,
  onMethodChange,
  onRangeChange,
  onSelect,
  onAction,
  actionNotice,
  drawer,
}: ResultsViewProps) {
  const { t, formatCurrency, formatNumber, formatPercent, formatDateTime } = useI18n();

  const eligibleCount = rows.filter((row) => row.compareEligible).length;
  const avgSavings = rows.filter((row) => row.savingsRate !== null).reduce((sum, row) => sum + (row.savingsRate ?? 0), 0) / Math.max(1, rows.filter((row) => row.savingsRate !== null).length);

  const tabs = useMemo<TabDefinition<ResultsViewProps['activeTab']>[]>(() => [
    { value: 'all', label: t('results.tabs.all'), count: allRows.length },
    { value: 'eligible', label: t('results.tabs.eligible'), count: allRows.filter((row) => row.compareEligible).length },
    { value: 'rejected', label: t('results.tabs.rejected'), count: allRows.filter((row) => !row.compareEligible).length },
    { value: 'best', label: t('results.tabs.best'), count: allRows.filter((row) => row.isBest).length },
  ], [allRows, t]);

  return (
    <section className="view-shell">
      <div className="view-subbar">
        <TabBar tabs={tabs} value={activeTab} onChange={onTabChange} ariaLabel={t('aria.viewTabs')} panelId="results-tabpanel" />
        <div className="subbar-filters" aria-label={t('aria.filterGroup')}>
          <FilterChip
            value={rangeFilter}
            onChange={onRangeChange}
            options={[
              { value: '24h', label: `${t('common.range')} · ${t('common.timeScope.24h')}` },
              { value: '7d', label: `${t('common.range')} · ${t('common.timeScope.7d')}` },
              { value: '30d', label: `${t('common.range')} · ${t('common.timeScope.30d')}` },
            ]}
          />
          <FilterChip
            value={sourceFilter}
            onChange={onSourceChange}
            options={[
              { value: 'all', label: `${t('common.source')} · ${t('common.filter.all')}` },
              { value: 'naver', label: `${t('common.source')} · ${t('common.source.naver')}` },
              { value: 'coupang', label: `${t('common.source')} · ${t('common.source.coupang')}` },
              { value: 'manual', label: `${t('common.source')} · ${t('common.source.manual')}` },
            ]}
          />
          <FilterChip
            value={methodFilter}
            onChange={onMethodChange}
            options={[
              { value: 'all', label: `${t('common.method')} · ${t('common.filter.all')}` },
              { value: 'shopping_api', label: `${t('common.method')} · ${t('common.method.shopping_api')}` },
              { value: 'parser_upload', label: `${t('common.method')} · ${t('common.method.parser_upload')}` },
              { value: 'manual_review', label: `${t('common.method')} · ${t('common.method.manual_review')}` },
            ]}
          />
          <button type="button" className="primary-action" onClick={() => onAction(t('results.actions.exportCsv'))}>{t('results.actions.exportCsv')}</button>
        </div>
      </div>
      {actionNotice ? <p className="action-notice">{actionNotice}</p> : null}

      <div className={`workspace ${drawer ? 'has-drawer' : ''}`}>
        <div className="workspace-main" role="tabpanel" id="results-tabpanel" aria-labelledby={`results-tabpanel-${activeTab}-tab`}>
          <div className="metric-strip results-grid">
            <MetricCard label={t('results.kpi.rows')} value={formatNumber(rows.length)} helper={`${t('common.source')} ${sourceFilter}`} tone="neutral" />
            <MetricCard label={t('results.kpi.eligibleRatio')} value={formatPercent(rows.length ? (eligibleCount / rows.length) * 100 : 0, 1)} helper={`${eligibleCount}/${rows.length || 0}`} tone="success" />
            <MetricCard label={t('results.kpi.partial')} value={formatNumber(new Set(rows.filter((row) => !row.compareEligible).map((row) => row.orderId)).size)} helper="QTY_MISMATCH / PARSER_AMBIGUOUS" tone="warning" />
            <MetricCard label={t('results.kpi.avgSavings')} value={avgSavings ? formatPercent(avgSavings, 1) : t('common.na')} helper={formatCurrency(rows.filter((row) => row.isBest).reduce((sum, row) => sum + row.perUnitPrice, 0) / Math.max(1, rows.filter((row) => row.isBest).length))} tone="amber" />
          </div>

          {rows.length === 0 ? <EmptyState /> : (
            <div className="table-scroll">
              <table className="ops-table">
                <thead>
                  <tr>
                    <th>{t('results.table.result')}</th>
                    <th>{t('results.table.orderProduct')}</th>
                    <th>{t('results.table.mallSeller')}</th>
                    <th>{t('results.table.source')}</th>
                    <th>{t('results.table.method')}</th>
                    <th>{t('results.table.perUnit')}</th>
                    <th>{t('results.table.listed')}</th>
                    <th>{t('results.table.eligible')}</th>
                    <th>{t('results.table.partialReason')}</th>
                    <th>{t('results.table.collected')}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} {...tableRowProps(row.id, selectedId)}>
                      <td className="mono-cell"><OpenDetailsButton id={row.id} label={`${t('common.openDetails')} ${row.id}`} onSelect={onSelect} />{row.isBest ? <span className="best-chip">{t('common.best')}</span> : null}</td>
                      <td>
                        <div className="table-primary">{row.productName}</div>
                        <div className="table-secondary">{row.orderId} · {row.jobId}</div>
                      </td>
                      <td>
                        <div className="table-primary">{row.mallName}</div>
                        <div className="table-secondary">{row.sellerCode}</div>
                      </td>
                      <td><SourceTag source={row.source} /></td>
                      <td className="mono-cell">{t(`common.method.${row.method}` as const)}</td>
                      <td>{formatCurrency(row.perUnitPrice)}</td>
                      <td>{formatCurrency(row.listedPrice)}</td>
                      <td>{row.compareEligible ? t('common.yes') : t('common.no')}</td>
                      <td className="mono-cell">{row.partialReason ?? t('common.na')}</td>
                      <td>{formatDateTime(row.collectedAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <FooterSummary visible={rows.length} total={allRows.length} />
        </div>
        {drawer}
      </div>
    </section>
  );
}

export function NotificationsView({
  rows,
  allRows,
  selectedId,
  activeTab,
  channelFilter,
  rangeFilter,
  onTabChange,
  onChannelChange,
  onRangeChange,
  onSelect,
  onAction,
  actionNotice,
  drawer,
}: NotificationsViewProps) {
  const { t, formatNumber, formatPercent, formatDateTime } = useI18n();

  const deliveredCount = rows.filter((row) => row.status === 'delivered').length;
  const fallbackCount = rows.filter((row) => row.status === 'fallback').length;
  const deadLetterCount = rows.filter((row) => row.status === 'dead-lettered').length;

  const tabs = useMemo<TabDefinition<NotificationsViewProps['activeTab']>[]>(() => [
    { value: 'all', label: t('notifications.tabs.all'), count: allRows.length },
    { value: 'inflight', label: t('notifications.tabs.inflight'), count: allRows.filter((row) => row.status === 'sending').length },
    { value: 'delivered', label: t('notifications.tabs.delivered'), count: allRows.filter((row) => row.status === 'delivered').length },
    { value: 'fallback', label: t('notifications.tabs.fallback'), count: allRows.filter((row) => row.status === 'fallback').length },
    { value: 'failed', label: t('notifications.tabs.failed'), count: allRows.filter((row) => row.status === 'dead-lettered').length },
  ], [allRows, t]);

  return (
    <section className="view-shell">
      <div className="view-subbar">
        <TabBar tabs={tabs} value={activeTab} onChange={onTabChange} ariaLabel={t('aria.viewTabs')} panelId="notifications-tabpanel" />
        <div className="subbar-filters" aria-label={t('aria.filterGroup')}>
          <FilterChip
            value={rangeFilter}
            onChange={onRangeChange}
            options={[
              { value: '24h', label: `${t('common.range')} · ${t('common.timeScope.24h')}` },
              { value: '7d', label: `${t('common.range')} · ${t('common.timeScope.7d')}` },
              { value: '30d', label: `${t('common.range')} · ${t('common.timeScope.30d')}` },
            ]}
          />
          <FilterChip
            value={channelFilter}
            onChange={onChannelChange}
            options={[
              { value: 'all', label: `${t('common.channel')} · ${t('common.filter.all')}` },
              { value: 'alimtalk', label: `${t('common.channel')} · ${t('common.channel.alimtalk')}` },
              { value: 'sms', label: `${t('common.channel')} · ${t('common.channel.sms')}` },
              { value: 'lms', label: `${t('common.channel')} · ${t('common.channel.lms')}` },
            ]}
          />
          <button type="button" className="primary-action" onClick={() => onAction(t('notifications.actions.traceOrder'))}>{t('notifications.actions.traceOrder')}</button>
        </div>
      </div>
      {actionNotice ? <p className="action-notice">{actionNotice}</p> : null}

      <div className={`workspace ${drawer ? 'has-drawer' : ''}`}>
        <div className="workspace-main" role="tabpanel" id="notifications-tabpanel" aria-labelledby={`notifications-tabpanel-${activeTab}-tab`}>
          <div className="metric-strip notifications-grid">
            <MetricCard label={t('notifications.kpi.lag')} value={t('notifications.kpi.lagValue')} helper={t('notifications.kpi.lagHelper')} tone="success" />
            <MetricCard label={t('notifications.kpi.deliveryRate')} value={formatPercent(rows.length ? (deliveredCount / rows.length) * 100 : 0, 1)} helper={`${deliveredCount}/${rows.length || 0}`} tone="amber" />
            <MetricCard label={t('notifications.kpi.fallback')} value={formatNumber(fallbackCount)} helper="kakao_blocked" tone="warning" />
            <MetricCard label={t('notifications.kpi.deadLetter')} value={formatNumber(deadLetterCount)} helper="recoverable 2 / 3" tone="danger" />
          </div>

          {rows.length === 0 ? <EmptyState /> : (
            <div className="table-scroll">
              <table className="ops-table">
                <thead>
                  <tr>
                    <th>{t('notifications.table.delivery')}</th>
                    <th>{t('notifications.table.trace')}</th>
                    <th>{t('notifications.table.channel')}</th>
                    <th>{t('notifications.table.template')}</th>
                    <th>{t('notifications.table.recipient')}</th>
                    <th>{t('notifications.table.status')}</th>
                    <th>{t('notifications.table.sent')}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} {...tableRowProps(row.id, selectedId)}>
                      <td className="mono-cell"><OpenDetailsButton id={row.id} label={`${t('common.openDetails')} ${row.id}`} onSelect={onSelect} /></td>
                      <td>
                        <div className="trace-inline">
                          <span>{row.jobId}</span>
                          <span className="trace-arrow">→</span>
                          <span>{row.resultId ?? 'partial'}</span>
                          <span className="trace-arrow">→</span>
                          <span>{row.outboxId}</span>
                          <span className="trace-arrow">→</span>
                          <span>{row.id}</span>
                        </div>
                      </td>
                      <td>{row.channel}{row.fallbackFrom ? ` ← ${row.fallbackFrom}` : ''}</td>
                      <td className="mono-cell">{row.templateName} · {row.templateVersion}</td>
                      <td>
                        <div className="table-primary">{row.recipientName}</div>
                        <div className="table-secondary">{row.recipientId} · {row.recipientPhone}</div>
                      </td>
                      <td><StatusPill label={t(`common.notificationStatus.${row.status}` as const)} tone={notificationTone(row.status)} /></td>
                      <td>{formatDateTime(row.sentAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <FooterSummary visible={rows.length} total={allRows.length} />
        </div>
        {drawer}
      </div>
    </section>
  );
}

export function ExperimentsView({
  rows,
  allRows,
  selectedId,
  activeTab,
  parserFilter,
  onTabChange,
  onParserChange,
  onSelect,
  onAction,
  actionNotice,
  drawer,
}: ExperimentsViewProps) {
  const { t, formatNumber, formatPercent, formatDateTime } = useI18n();

  const totalItems = rows.reduce((sum, row) => sum + row.itemCount, 0);
  const acceptedItems = rows.reduce((sum, row) => sum + row.acceptedCount, 0);

  const tabs = useMemo<TabDefinition<ExperimentsViewProps['activeTab']>[]>(() => [
    { value: 'uploads', label: t('experiments.tabs.uploads'), count: allRows.filter((row) => row.type === 'uploads').length },
    { value: 'parse-runs', label: t('experiments.tabs.parse-runs'), count: allRows.filter((row) => row.type === 'parse-runs').length },
    { value: 'compare', label: t('experiments.tabs.compare'), count: allRows.filter((row) => row.type === 'compare').length },
    { value: 'regressions', label: t('experiments.tabs.regressions'), count: allRows.filter((row) => row.type === 'regressions').length },
  ], [allRows, t]);

  return (
    <section className="view-shell">
      <div className="experiment-banner">
        <strong>{t('experiments.banner.label')}</strong>
        <p>{t('experiments.banner.body')}</p>
        <button type="button" className="ghost-link" onClick={() => onAction(t('experiments.banner.link'))}>{t('experiments.banner.link')}</button>
      </div>

      <div className="view-subbar">
        <TabBar tabs={tabs} value={activeTab} onChange={onTabChange} ariaLabel={t('aria.viewTabs')} panelId="experiments-tabpanel" />
        <div className="subbar-filters" aria-label={t('aria.filterGroup')}>
          <FilterChip
            value={parserFilter}
            onChange={onParserChange}
            options={[
              { value: 'all', label: `${t('common.parser')} · ${t('common.filter.all')}` },
              { value: 'current', label: `${t('common.parser')} · ${t('common.filter.current')}` },
            ]}
          />
          <button type="button" className="primary-action" onClick={() => onAction(t('experiments.actions.uploadBatch'))}>{t('experiments.actions.uploadBatch')}</button>
        </div>
      </div>
      {actionNotice ? <p className="action-notice">{actionNotice}</p> : null}

      <div className={`workspace ${drawer ? 'has-drawer' : ''}`}>
        <div className="workspace-main" role="tabpanel" id="experiments-tabpanel" aria-labelledby={`experiments-tabpanel-${activeTab}-tab`}>
          <div className="metric-strip experiments-grid">
            <MetricCard label={t('experiments.kpi.uploads')} value={formatNumber(rows.length)} helper={t('experiments.kpi.uploadHelper')} tone="warning" />
            <MetricCard label={t('experiments.kpi.parseSuccess')} value={formatPercent(totalItems ? (acceptedItems / totalItems) * 100 : 0, 1)} helper={`${acceptedItems}/${Math.max(totalItems, 1)}`} tone="neutral" />
            <MetricCard label={t('experiments.kpi.diverged')} value={formatNumber(rows.filter((row) => row.compareSummary.includes('+')).length)} helper={t('experiments.kpi.divergedHelper')} tone="amber" />
            <MetricCard label={t('experiments.kpi.isolation')} value={t('common.env.experimentCode')} helper={t('experiments.kpi.isolationHelper')} tone="success" />
          </div>

          {rows.length === 0 ? <EmptyState /> : (
            <div className="table-scroll">
              <table className="ops-table">
                <thead>
                  <tr>
                    <th>{t('experiments.table.run')}</th>
                    <th>{t('experiments.table.env')}</th>
                    <th>{t('experiments.table.uploaded')}</th>
                    <th>{t('experiments.table.source')}</th>
                    <th>{t('experiments.table.uploader')}</th>
                    <th>{t('experiments.table.parser')}</th>
                    <th>{t('experiments.table.items')}</th>
                    <th>{t('experiments.table.accepted')}</th>
                    <th>{t('experiments.table.compare')}</th>
                    <th>{t('experiments.table.uploadedAt')}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} {...tableRowProps(row.id, selectedId)}>
                      <td className="mono-cell"><OpenDetailsButton id={row.id} label={`${t('common.openDetails')} ${row.id}`} onSelect={onSelect} /></td>
                      <td><span className="env-pill">{t('common.env.experimentCode')}</span></td>
                      <td>
                        <div className="table-primary">{row.name}</div>
                        <div className="table-secondary">{row.type}</div>
                      </td>
                      <td><SourceTag source={row.source} /></td>
                      <td className="mono-cell">{row.uploader}</td>
                      <td className="mono-cell">{row.parserVersion}</td>
                      <td>{formatNumber(row.itemCount)}</td>
                      <td>{formatNumber(row.acceptedCount)}</td>
                      <td className="mono-cell">{row.compareSummary}</td>
                      <td>{formatDateTime(row.uploadedAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <FooterSummary visible={rows.length} total={allRows.length} />
        </div>
        {drawer}
      </div>
    </section>
  );
}
