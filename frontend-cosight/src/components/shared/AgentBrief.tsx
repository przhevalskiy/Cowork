/**
 * AgentBrief — lightweight, client-side insight strip shown when dashboard data loads.
 * Surfaces the biggest KPI move so the page feels agentic without an LLM round-trip.
 */
import React, { useMemo } from 'react';
import { CoSightGlyph } from '../chat/CoSightGlyph';
import type { NormalizedMetric } from '../../types';
import { formatCount, formatPercent } from '../../utils/formatNumber';
import './AgentBrief.css';

interface Props {
  summary: NormalizedMetric[];
  /** Optional second line (e.g. data freshness caveats) */
  note?: string;
  isLoading?: boolean;
  loadingLabel?: string;
}

function formatMetricValue(metric: NormalizedMetric): string {
  if (metric.unit === 'percent' || metric.unit === 'rate') {
    return formatPercent(metric.unit === 'rate' ? metric.value * 100 : metric.value);
  }
  return formatCount(metric.value);
}

function buildHeadline(summary: NormalizedMetric[]): string | null {
  const kpis = summary.filter(m => !m.dimension && !m.date_bucket && m.delta_pct != null);
  if (kpis.length === 0) return null;

  const top = [...kpis].sort((a, b) => Math.abs(b.delta_pct!) - Math.abs(a.delta_pct!))[0];
  const label = top.label || top.metric_key.replace(/_/g, ' ');
  const dir = top.delta_pct! >= 0 ? 'up' : 'down';
  return `${label} is ${dir} ${Math.abs(top.delta_pct!).toFixed(1)}% vs the prior period (${formatMetricValue(top)}).`;
}

export const AgentBrief: React.FC<Props> = ({ summary, note, isLoading, loadingLabel }) => {
  const headline = useMemo(() => buildHeadline(summary), [summary]);

  if (isLoading) {
    return (
      <div className="agent-brief agent-brief--loading">
        <CoSightGlyph state="loading" size={22} />
        <p>{loadingLabel || 'CoSight is pulling your latest metrics…'}</p>
      </div>
    );
  }

  if (!headline && !note) return null;

  return (
    <div className="agent-brief">
      <CoSightGlyph state="done" size={22} />
      <div className="agent-brief__text">
        {headline && <p className="agent-brief__headline">{headline}</p>}
        {note && <p className="agent-brief__note">{note}</p>}
      </div>
    </div>
  );
};
