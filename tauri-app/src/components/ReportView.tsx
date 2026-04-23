import type { SummaryReport } from '../types/api';
import type { ComparisonResult } from '../types/procurement';
import { formatKrw } from '../utils/format';
import { calculateReportMetrics } from '../utils/procurement';

interface ReportViewProps {
  results: ComparisonResult[];
  apiReport?: SummaryReport | null;
  onRefreshReport?: () => void;
  canRefresh?: boolean;
}

function toNumber(value: string | number | null | undefined): number {
  if (value === null || value === undefined) return 0;
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function ReportView({ results, apiReport, onRefreshReport, canRefresh = false }: ReportViewProps) {
  const report = calculateReportMetrics(results);
  const maxSaved = Math.max(1, ...report.monthly.map((item) => item.saved));

  return (
    <section className="panel report-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Step 3</p>
          <h2>절감 리포트</h2>
        </div>
        <div className="inline-actions inline-actions--compact">
          {apiReport ? <span className="pill pill--accent">API 집계 연결됨</span> : <span className="pill">로컬 추정치</span>}
          <button className="button button--ghost" disabled={!canRefresh} onClick={onRefreshReport}>API 리포트 새로고침</button>
        </div>
      </div>
      <p className="muted-copy">품목별 목표 단가와 최저 실가 차이를 기준으로 추정합니다.</p>

      {apiReport ? (
        <div className="api-report-strip">
          <strong>백엔드 누적 집계</strong>
          <span>발주 {apiReport.orders_count}건</span>
          <span>결과 {apiReport.results_count}건</span>
          <span>총 절감액 {formatKrw(toNumber(apiReport.total_savings))}</span>
        </div>
      ) : null}

      <div className="metric-grid">
        {report.metrics.map((metric) => (
          <article key={metric.label} className="metric-card">
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <small>{metric.helper}</small>
          </article>
        ))}
      </div>

      <div className="bar-chart" aria-label="월별 절감액 차트">
        {report.monthly.map((point) => (
          <div key={point.month} className="bar-chart__item">
            <div className="bar-chart__bar" style={{ height: `${Math.max(8, (point.saved / maxSaved) * 100)}%` }} />
            <span>{point.month}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
