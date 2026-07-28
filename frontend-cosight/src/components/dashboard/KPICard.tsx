/**
 * KPI Card — metric name, value, delta vs prior period, trend arrow.
 * Delta/prior_value come from the connector layer, never computed here.
 * Invariant: if delta comes from this component it's a bug.
 */
import React from 'react';
import type { NormalizedMetric, ScopedContext, DateRange } from '../../types';
import './KPICard.css';

interface Props {
  metric: NormalizedMetric;
  dateRange?: DateRange;
  onDrillIn?: (ctx: ScopedContext) => void;
}

function formatValue(metric: NormalizedMetric): string {
  const { value, unit } = metric;
  if (unit === 'percent') return `${value.toFixed(1)}%`;
  if (unit === 'rate') return `${(value * 100).toFixed(1)}%`;
  if (unit === 'position') return value.toFixed(1);
  if (unit === 'duration') {
    const mins = Math.floor(value / 60);
    const secs = Math.round(value % 60);
    return `${mins}m ${secs}s`;
  }
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toFixed(0);
}

export const KPICard: React.FC<Props> = ({ metric, dateRange, onDrillIn }) => {
  const label = metric.label || metric.metric_key.replace(/_/g, ' ');
  const hasDelta = metric.delta_pct !== undefined && metric.delta_pct !== null;
  const isPositive = hasDelta && metric.delta_pct! > 0;
  // For position metrics, lower is better — invert the color
  const isPositivePosition = metric.unit === 'position' ? !isPositive : isPositive;

  const handleDrillIn = () => {
    if (!onDrillIn) return;
    onDrillIn({
      channel: metric.channel,
      metric_key: metric.metric_key,
      date_range: dateRange ? `${dateRange.start}/${dateRange.end}` : undefined,
      value: metric.value,
      delta: metric.delta_pct,
    });
  };

  return (
    <div className={`kpi-card ${onDrillIn ? 'kpi-card--drillable' : ''}`}>
      <div className="kpi-card__label">{label}</div>
      <div className="kpi-card__value">{formatValue(metric)}</div>
      {hasDelta && (
        <div className={`kpi-card__delta ${isPositivePosition ? 'delta--up' : 'delta--down'}`}>
          <span className="delta-arrow">{isPositivePosition ? '↑' : '↓'}</span>
          {Math.abs(metric.delta_pct!).toFixed(1)}% vs prior period
        </div>
      )}
      {onDrillIn && (
        <button className="kpi-card__ask" onClick={handleDrillIn} title="Ask CoSight about this metric">
          Ask about this ✦
        </button>
      )}
    </div>
  );
};
