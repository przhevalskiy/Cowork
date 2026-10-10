/**
 * Context payloads for section-level SSE insights.
 */
import type { NormalizedMetric } from '../types';
import { formatCount, formatMetricValue } from './formatNumber';

export function kpiInsightContext(metric: NormalizedMetric): Record<string, unknown> {
  return {
    type: 'kpi',
    metric_key: metric.metric_key,
    label: metric.label || metric.metric_key.replace(/_/g, ' '),
    value: metric.value,
    formatted_value: formatMetricValue(metric.value, metric.unit),
    delta_pct: metric.delta_pct ?? null,
    unit: metric.unit,
  };
}

function seriesStats(
  timeseries: NormalizedMetric[],
  key: string,
  label: string,
): Record<string, unknown> | null {
  const points = timeseries
    .filter(m => m.metric_key === key && m.date_bucket)
    .sort((a, b) => String(a.date_bucket).localeCompare(String(b.date_bucket)));
  if (points.length === 0) return null;
  const start = points[0].value;
  const end = points[points.length - 1].value;
  const change = start !== 0 ? ((end - start) / Math.abs(start)) * 100 : null;
  return {
    key,
    label,
    start_value: start,
    end_value: end,
    formatted_start: formatCount(start),
    formatted_end: formatCount(end),
    change_pct: change,
    days: points.length,
  };
}

export function timeseriesInsightContext(
  title: string,
  timeseries: NormalizedMetric[],
  series: Array<{ key: string; label: string }>,
): Record<string, unknown> {
  const stats = series
    .map(s => seriesStats(timeseries, s.key, s.label))
    .filter(Boolean);
  return {
    type: 'timeseries',
    title,
    series: stats,
  };
}

export function platformBreakdownContext(metrics: NormalizedMetric[]): Record<string, unknown> {
  const byPlatform = new Map<string, NormalizedMetric[]>();
  for (const m of metrics) {
    if (!m.dimension) continue;
    const list = byPlatform.get(m.dimension) ?? [];
    list.push(m);
    byPlatform.set(m.dimension, list);
  }

  const rows: Array<Record<string, unknown>> = [];
  for (const [platform, platformMetrics] of byPlatform) {
    const imps = platformMetrics.find(m => m.metric_key === 'impressions');
    if (!imps) continue;
    rows.push({
      platform,
      impressions: imps.value,
      formatted_impressions: formatCount(imps.value),
      delta_pct: imps.delta_pct ?? null,
    });
  }

  rows.sort((a, b) => (b.impressions as number) - (a.impressions as number));
  const total = rows.reduce((s, r) => s + (r.impressions as number), 0);
  for (const row of rows) {
    row.impression_share = total > 0 ? ((row.impressions as number) / total) * 100 : 0;
  }

  return {
    type: 'platform_breakdown',
    title: 'By Platform',
    platforms: rows.slice(0, 6),
  };
}

export function tableInsightContext(
  title: string,
  rowCount: number,
  highlight?: string,
): Record<string, unknown> {
  return {
    type: 'table',
    title,
    row_count: rowCount,
    highlight: highlight ?? null,
  };
}
