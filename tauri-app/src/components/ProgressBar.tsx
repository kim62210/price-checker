import type { ProcurementProgress } from '../types/procurement';
import { formatPercent } from '../utils/format';
import { StatusBadge } from './StatusBadge';

interface ProgressBarProps {
  progress: ProcurementProgress;
}

export function ProgressBar({ progress }: ProgressBarProps) {
  return (
    <section className="panel progress-panel" aria-label="조회 진행률">
      <div className="section-heading">
        <div>
          <p className="eyebrow">실시간 조회</p>
          <h2>조회 진행률</h2>
        </div>
        <strong>{progress.current}/{progress.total || 0}</strong>
      </div>
      <div className="progress-track" aria-label={`진행률 ${formatPercent(progress.percent)}`}>
        <div className="progress-track__fill" style={{ width: formatPercent(progress.percent) }} />
      </div>
      <div className="platform-progress">
        {progress.platforms.map((platform) => (
          <div key={platform.platform} className="platform-progress__item">
            <span>{platform.label}</span>
            <StatusBadge status={platform.status} />
          </div>
        ))}
      </div>
    </section>
  );
}
