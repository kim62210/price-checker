import type { WorkflowStatus } from '../types/procurement';
import { statusMeta } from '../utils/procurement';

interface StatusBadgeProps {
  status: WorkflowStatus;
  compact?: boolean;
}

export function StatusBadge({ status, compact = false }: StatusBadgeProps) {
  const meta = statusMeta(status);
  return (
    <span className={`status-badge status-badge--${meta.tone}`} title={meta.helper}>
      <span className="status-badge__dot" />
      {compact ? meta.label : <span>{meta.label}</span>}
    </span>
  );
}
