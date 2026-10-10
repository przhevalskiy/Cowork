import React, { useEffect, useState } from 'react';
import { KPICard } from './KPICard';
import type { NormalizedMetric, ScopedContext, DateRange } from '../../types';
import './StaggeredKPIGrid.css';

interface Props {
  metrics: NormalizedMetric[];
  visible: boolean;
  dateRange?: DateRange;
  onDrillIn?: (ctx: ScopedContext) => void;
  onComplete?: () => void;
  staggerMs?: number;
}

export const StaggeredKPIGrid: React.FC<Props> = ({
  metrics,
  visible,
  dateRange,
  onDrillIn,
  onComplete,
  staggerMs = 120,
}) => {
  const [shownCount, setShownCount] = useState(0);

  useEffect(() => {
    if (!visible) {
      setShownCount(0);
      return;
    }
    if (shownCount >= metrics.length) {
      onComplete?.();
      return;
    }
    const t = window.setTimeout(() => setShownCount(c => c + 1), staggerMs);
    return () => window.clearTimeout(t);
  }, [visible, shownCount, metrics.length, staggerMs, onComplete]);

  if (!visible) return null;

  return (
    <div className="kpi-grid staggered-kpi-grid">
      {metrics.slice(0, shownCount).map((m, i) => (
        <div
          key={`${m.metric_key}-${m.dimension ?? ''}-${i}`}
          className="staggered-kpi-grid__item"
          style={{ animationDelay: '0ms' }}
        >
          <KPICard metric={m} dateRange={dateRange} onDrillIn={onDrillIn} />
        </div>
      ))}
    </div>
  );
};
