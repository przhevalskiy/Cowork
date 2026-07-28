/**
 * CoSight canonical types — mirror the backend Pydantic models exactly.
 * All dashboard components and AI tools consume only these shapes.
 */

export type Channel = 'social' | 'email' | 'web' | 'search';
export type MetricUnit = 'count' | 'rate' | 'percent' | 'position' | 'duration' | 'currency';
export type ChannelStatus = 'ok' | 'stale' | 'error';

export interface NormalizedMetric {
  channel: Channel;
  metric_key: string;
  label?: string;
  value: number;
  prior_value?: number;
  delta_pct?: number;
  date_bucket?: string;
  unit: MetricUnit;
  dimension?: string;
}

export interface ChannelMetrics {
  channel: Channel;
  start_date: string;
  end_date: string;
  summary: NormalizedMetric[];
  timeseries: NormalizedMetric[];
  status: ChannelStatus;
  error_message?: string;
  cached_at?: string;
}

export interface OverviewPayload {
  web?: ChannelMetrics;
  /** GSC search channel — returned as key 'search' from backend */
  search?: ChannelMetrics;
  email?: ChannelMetrics;
  social?: ChannelMetrics;
}

// ── Report artifact types ─────────────────────────────────────────────────────

export interface ChartSpec {
  chart_type: 'line' | 'bar' | 'area';
  title: string;
  metric_keys: string[];
  x_axis: string;
  y_axis_label?: string;
  dual_axis: boolean;
}

export interface ReportSection {
  id: string;
  title: string;
  channel?: string;
  narrative?: string;
  kpis: NormalizedMetric[];
  charts: ChartSpec[];
  table_rows: Record<string, unknown>[];
  table_headers: string[];
}

export interface ReportArtifact {
  id?: string;
  title: string;
  subtitle?: string;
  date_range_start: string;
  date_range_end: string;
  sections: ReportSection[];
  executive_summary?: string;
  created_at?: string;
  created_by?: string;
}

// ── Chat types ────────────────────────────────────────────────────────────────

export interface ScopedContext {
  channel?: Channel;
  metric_key?: string;
  /** Human-readable label for the metric, used in the drill-in opening message */
  label?: string;
  date_range?: string;
  value?: number;
  delta?: number;
}

export interface CoSightMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  tools_called?: string[];
  report?: ReportArtifact;
}

export interface DateRange {
  start: string;
  end: string;
}
