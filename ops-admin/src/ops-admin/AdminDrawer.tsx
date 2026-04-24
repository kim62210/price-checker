import { useEffect, useMemo, useState } from 'react';

import { useI18n } from '../i18n';
import { isLocalizedText } from './types';
import type { DisplayText, ExperimentRow, JobRow, NotificationRow, ResultRow, ViewId } from './types';

interface AdminDrawerProps {
  view: ViewId;
  entity: JobRow | ResultRow | NotificationRow | ExperimentRow;
  onClose: () => void;
}

function getDefaultTab(view: ViewId): string {
  switch (view) {
    case 'jobs':
      return 'overview';
    case 'results':
      return 'overview';
    case 'notifications':
      return 'lineage';
    case 'experiments':
      return 'overview';
  }
}

function jsonPreview(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function isJob(entity: AdminDrawerProps['entity']): entity is JobRow {
  return 'attempts' in entity;
}

function isResult(entity: AdminDrawerProps['entity']): entity is ResultRow {
  return 'compareEligible' in entity;
}

function isNotification(entity: AdminDrawerProps['entity']): entity is NotificationRow {
  return 'eventCode' in entity;
}

function isExperiment(entity: AdminDrawerProps['entity']): entity is ExperimentRow {
  return 'acceptedCount' in entity;
}

function localizeText(value: DisplayText, locale: 'ko' | 'en'): string {
  return isLocalizedText(value) ? value[locale] : value;
}

function getDrawerTitle(entity: AdminDrawerProps['entity']): string {
  if (isJob(entity) || isResult(entity)) {
    return entity.productName;
  }

  if (isNotification(entity)) {
    return entity.eventCode;
  }

  return entity.name;
}

export function AdminDrawer({ view, entity, onClose }: AdminDrawerProps) {
  const { locale, t, formatCurrency, formatDateTime, formatNumber } = useI18n();
  const [activeTab, setActiveTab] = useState(getDefaultTab(view));
  const tabPanelId = `drawer-tabpanel-${view}-${activeTab}`;

  useEffect(() => {
    setActiveTab(getDefaultTab(view));
  }, [view, entity]);

  const tabs = useMemo(() => {
    if (view === 'jobs') {
      return [
        { id: 'overview', label: t('jobs.drawer.tab.overview') },
        { id: 'timeline', label: t('jobs.drawer.tab.timeline') },
        { id: 'raw', label: t('jobs.drawer.tab.raw') },
      ];
    }

    if (view === 'results') {
      return [
        { id: 'overview', label: t('results.drawer.tab.overview') },
        { id: 'siblings', label: t('results.drawer.tab.siblings') },
        { id: 'raw', label: t('results.drawer.tab.raw') },
        { id: 'notification', label: t('results.drawer.tab.notification') },
      ];
    }

    if (view === 'notifications') {
      return [
        { id: 'lineage', label: t('notifications.drawer.tab.lineage') },
        { id: 'variables', label: t('notifications.drawer.tab.variables') },
        { id: 'provider', label: t('notifications.drawer.tab.provider') },
      ];
    }

    return [
      { id: 'overview', label: t('experiments.drawer.tab.overview') },
      { id: 'comparison', label: t('experiments.drawer.tab.comparison') },
      { id: 'raw', label: t('experiments.drawer.tab.raw') },
    ];
  }, [t, view]);

  return (
    <aside className="drawer-panel" aria-label={t('aria.drawer')}>
      <header className="drawer-header">
        <div className="drawer-topline">
          <span className="drawer-eyebrow">
            {view === 'jobs'
              ? t('jobs.drawer.eyebrow')
              : view === 'results'
                ? t('results.drawer.eyebrow')
                : view === 'notifications'
                  ? t('notifications.drawer.eyebrow')
                  : t('experiments.drawer.eyebrow')}
          </span>
          <button className="icon-button" type="button" onClick={onClose} aria-label={t('aria.closeDrawer')}>
            ×
          </button>
        </div>
        <h2 className="drawer-title">{entity.id} · {getDrawerTitle(entity)}</h2>
        <div className="drawer-meta">
          {'orderId' in entity ? <span>{entity.orderId}</span> : null}
          {'jobId' in entity ? <span>{entity.jobId}</span> : null}
          {'source' in entity ? <span>{entity.source}</span> : null}
        </div>
        <div className="drawer-tabs" role="tablist" aria-label={t('aria.viewTabs')}>
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={activeTab === tab.id}
              aria-controls={`drawer-tabpanel-${view}-${tab.id}`}
              id={`drawer-tab-${view}-${tab.id}`}
              className={`drawer-tab ${activeTab === tab.id ? 'is-active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </header>

      <div className="drawer-body" role="tabpanel" id={tabPanelId} aria-labelledby={`drawer-tab-${view}-${activeTab}`}>
        {isJob(entity) ? (
          <>
            {activeTab === 'overview' ? (
              <>
                <section className="drawer-section">
                  <h3>{t('jobs.drawer.section.summary')}</h3>
                  <dl className="detail-grid">
                    <div><dt>{t('jobs.drawer.summary.targetUnitPrice')}</dt><dd>{entity.detail.targetUnitPrice ? formatCurrency(entity.detail.targetUnitPrice) : t('common.na')}</dd></div>
                    <div><dt>{t('jobs.drawer.summary.queueDepth')}</dt><dd>{formatNumber(entity.detail.queueDepth)}</dd></div>
                    <div><dt>{t('jobs.drawer.summary.duration')}</dt><dd>{entity.detail.durationSeconds ? `${entity.detail.durationSeconds}s` : t('label.inFlight')}</dd></div>
                    <div><dt>{t('jobs.drawer.summary.policy')}</dt><dd>{localizeText(entity.detail.policy, locale)}</dd></div>
                    <div><dt>{t('jobs.drawer.summary.kept')}</dt><dd>{entity.detail.keptResults !== null && entity.detail.totalResults !== null ? `${entity.detail.keptResults} / ${entity.detail.totalResults}` : t('common.na')}</dd></div>
                    <div><dt>{t('jobs.drawer.summary.nextRetry')}</dt><dd>{entity.nextRetryAt ? formatDateTime(entity.nextRetryAt) : entity.finishedAt ? formatDateTime(entity.finishedAt) : t('common.na')}</dd></div>
                  </dl>
                </section>
                {entity.lastErrorCode && entity.lastErrorMessage ? (
                  <section className="drawer-section">
                    <h3>{t('jobs.drawer.section.error')}</h3>
                    <div className="error-block">
                      <strong>{entity.lastErrorCode}</strong>
                      <p>{localizeText(entity.lastErrorMessage, locale)}</p>
                    </div>
                  </section>
                ) : null}
              </>
            ) : null}

            {activeTab === 'timeline' ? (
              <section className="drawer-section">
                <h3>{t('jobs.drawer.section.timeline')}</h3>
                <ol className="timeline-list">
                  {entity.detail.timeline.map((item) => (
                    <li key={item.id} className={`timeline-item tone-${item.tone}`}>
                      <div className="timeline-title-row">
                        <strong>{localizeText(item.title, locale)}</strong>
                        <span>{formatDateTime(item.timestamp)}</span>
                      </div>
                      <p>{localizeText(item.detail, locale)}</p>
                    </li>
                  ))}
                </ol>
              </section>
            ) : null}

            {activeTab === 'raw' ? (
              <section className="drawer-section">
                <h3>{t('label.rawPayload')}</h3>
                <pre className="code-panel">{jsonPreview(entity.detail.rawPayload)}</pre>
              </section>
            ) : null}
          </>
        ) : null}

        {isResult(entity) ? (
          <>
            {activeTab === 'overview' ? (
              <>
                <section className="drawer-section">
                  <h3>{t('results.drawer.section.pricing')}</h3>
                  <dl className="detail-grid">
                    <div><dt>{t('results.drawer.summary.perUnitPrice')}</dt><dd>{formatCurrency(entity.perUnitPrice)}</dd></div>
                    <div><dt>{t('results.drawer.summary.listedPrice')}</dt><dd>{formatCurrency(entity.listedPrice)}</dd></div>
                    <div><dt>{t('results.drawer.summary.shippingFee')}</dt><dd>{formatCurrency(entity.shippingFee)}</dd></div>
                    <div><dt>{t('results.drawer.summary.unitCount')}</dt><dd>{entity.unitCount}{entity.unitLabel}</dd></div>
                    <div><dt>{t('results.drawer.summary.totalPrice')}</dt><dd>{formatCurrency(entity.listedPrice + entity.shippingFee)}</dd></div>
                    <div><dt>{t('results.drawer.summary.targetUnitPrice')}</dt><dd>{formatCurrency(entity.detail.targetUnitPrice)}</dd></div>
                  </dl>
                </section>
                <section className="drawer-section">
                  <h3>{t('results.drawer.section.provenance')}</h3>
                  <dl className="detail-grid">
                    <div><dt>{t('results.drawer.summary.mall')}</dt><dd>{entity.mallName}</dd></div>
                    <div><dt>{t('results.drawer.summary.seller')}</dt><dd>{entity.sellerCode}</dd></div>
                    <div><dt>{t('results.drawer.summary.collectedAt')}</dt><dd>{formatDateTime(entity.collectedAt)}</dd></div>
                    <div><dt>{t('results.drawer.summary.eligible')}</dt><dd>{entity.compareEligible ? t('common.yes') : t('common.no')}</dd></div>
                  </dl>
                  <div className="note-list">
                    <span className="note-list__label">{t('label.validatorNotes')}</span>
                    <ul>
                      {entity.detail.validatorNotes.map((note) => <li key={localizeText(note, 'en')}>{localizeText(note, locale)}</li>)}
                    </ul>
                  </div>
                </section>
              </>
            ) : null}

            {activeTab === 'siblings' ? (
              <section className="drawer-section">
                <h3>{t('results.drawer.section.siblings')}</h3>
                <table className="mini-table">
                  <thead>
                    <tr>
                      <th>{t('results.table.mallSeller')}</th>
                      <th>{t('results.table.perUnit')}</th>
                      <th>{t('results.table.eligible')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {entity.detail.siblings.map((sibling) => (
                      <tr key={sibling.id}>
                        <td>{sibling.mall} · {sibling.seller}</td>
                        <td>{formatCurrency(sibling.perUnitPrice)}</td>
                        <td>{sibling.eligible ? t('common.yes') : t('common.no')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            ) : null}

            {activeTab === 'raw' ? (
              <section className="drawer-section">
                <h3>{t('label.rawPayload')}</h3>
                <pre className="code-panel">{jsonPreview(entity.detail.rawPayload)}</pre>
              </section>
            ) : null}

            {activeTab === 'notification' ? (
              <section className="drawer-section">
                <h3>{t('results.drawer.tab.notification')}</h3>
                <p>
                  {entity.detail.notificationId
                    ? t('results.drawer.notificationLinked', { id: entity.detail.notificationId })
                    : t('results.drawer.notificationNone')}
                </p>
              </section>
            ) : null}
          </>
        ) : null}

        {isNotification(entity) ? (
          <>
            {activeTab === 'lineage' ? (
              <section className="drawer-section">
                <h3>{t('notifications.drawer.section.timeline')}</h3>
                <ol className="timeline-list">
                  {entity.detail.timeline.map((item) => (
                    <li key={item.id} className={`timeline-item tone-${item.tone}`}>
                      <div className="timeline-title-row">
                        <strong>{localizeText(item.title, locale)}</strong>
                        <span>{formatDateTime(item.timestamp)}</span>
                      </div>
                      <p>{localizeText(item.detail, locale)}</p>
                    </li>
                  ))}
                </ol>
              </section>
            ) : null}

            {activeTab === 'variables' ? (
              <section className="drawer-section">
                <h3>{t('notifications.drawer.section.variables')}</h3>
                <pre className="code-panel">{jsonPreview(entity.detail.renderedVariables)}</pre>
              </section>
            ) : null}

            {activeTab === 'provider' ? (
              <section className="drawer-section">
                <h3>{t('notifications.drawer.section.provider')}</h3>
                <table className="mini-table">
                  <thead>
                    <tr>
                      <th>{t('notifications.table.channel')}</th>
                      <th>{t('notifications.table.status')}</th>
                      <th>{t('notifications.table.sent')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {entity.detail.providerAttempts.map((attempt) => (
                      <tr key={attempt.id}>
                        <td>{attempt.channel} · {attempt.provider}</td>
                        <td>{attempt.status}</td>
                        <td>{formatDateTime(attempt.timestamp)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            ) : null}
          </>
        ) : null}

        {isExperiment(entity) ? (
          <>
            {activeTab === 'overview' ? (
              <>
                <section className="drawer-section">
                  <h3>{t('experiments.drawer.section.isolation')}</h3>
                  <dl className="detail-grid">
                    <div><dt>{t('experiments.drawer.summary.schema')}</dt><dd>{entity.detail.isolatedSchemas.join(', ')}</dd></div>
                    <div><dt>{t('experiments.drawer.summary.excluded')}</dt><dd>{entity.detail.excludedPipelines.join(', ')}</dd></div>
                    <div><dt>{t('experiments.drawer.summary.retention')}</dt><dd>{localizeText(entity.detail.retention, locale)}</dd></div>
                    <div><dt>{t('experiments.drawer.summary.notes')}</dt><dd>{entity.detail.notes.map((note) => localizeText(note, locale)).join(' · ')}</dd></div>
                  </dl>
                </section>
                <section className="drawer-section">
                  <h3>{t('experiments.drawer.section.summary')}</h3>
                  <dl className="detail-grid">
                    <div><dt>{t('experiments.table.items')}</dt><dd>{formatNumber(entity.itemCount)}</dd></div>
                    <div><dt>{t('experiments.table.accepted')}</dt><dd>{formatNumber(entity.acceptedCount)}</dd></div>
                    <div><dt>{t('experiments.table.parser')}</dt><dd>{entity.parserVersion}</dd></div>
                    <div><dt>{t('experiments.table.uploader')}</dt><dd>{entity.uploader}</dd></div>
                  </dl>
                </section>
              </>
            ) : null}

            {activeTab === 'comparison' ? (
              <section className="drawer-section">
                <h3>{t('experiments.drawer.section.compare')}</h3>
                <table className="mini-table">
                  <thead>
                    <tr>
                      <th>{t('experiments.drawer.compare.metric')}</th>
                      <th>{t('experiments.drawer.compare.left')}</th>
                      <th>{t('experiments.drawer.compare.right')}</th>
                      <th>{t('experiments.drawer.compare.delta')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {entity.detail.comparisonMetrics.map((metric) => (
                      <tr key={metric.id}>
                        <td>{localizeText(metric.label, locale)}</td>
                        <td>{localizeText(metric.leftValue, locale)}</td>
                        <td>{localizeText(metric.rightValue, locale)}</td>
                        <td>{localizeText(metric.delta, locale)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            ) : null}

            {activeTab === 'raw' ? (
              <section className="drawer-section">
                <h3>{t('label.rawPayload')}</h3>
                <pre className="code-panel">{jsonPreview(entity.detail.rawPayload)}</pre>
              </section>
            ) : null}
          </>
        ) : null}
      </div>
    </aside>
  );
}
