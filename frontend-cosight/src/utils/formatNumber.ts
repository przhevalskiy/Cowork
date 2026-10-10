import type { MetricUnit } from '../types';

/** Whole numbers with locale commas (e.g. 1,234,567). */
export function formatCount(value: number): string {
  if (!Number.isFinite(value)) return '—';
  return Math.round(value).toLocaleString('en-US');
}

export function formatPercent(value: number, decimals = 1): string {
  if (!Number.isFinite(value)) return '—';
  return `${value.toFixed(decimals)}%`;
}

export function formatMetricValue(value: number, unit: MetricUnit): string {
  switch (unit) {
    case 'percent':
      return formatPercent(value);
    case 'rate':
      return formatPercent(value * 100);
    case 'position':
      return value.toFixed(1);
    case 'duration': {
      const mins = Math.floor(value / 60);
      const secs = Math.round(value % 60);
      return `${mins}m ${secs}s`;
    }
    case 'currency':
      return value.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
    default:
      return formatCount(value);
  }
}

/** Compact axis labels — comma-separated, no K/M abbreviation. */
export function formatAxisCount(value: number): string {
  if (!Number.isFinite(value)) return '';
  return Math.round(value).toLocaleString('en-US');
}
