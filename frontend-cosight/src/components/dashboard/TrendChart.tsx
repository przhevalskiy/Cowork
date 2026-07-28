/**
 * TrendChart — Recharts line chart with multi-series, dual-axis, and PNG download.
 * Chart image export is client-side (SVG → PNG via html-to-image).
 */
import React, { useRef } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer,
} from 'recharts';
import { toPng } from 'html-to-image';
import type { NormalizedMetric } from '../../types';
import './TrendChart.css';

interface Series {
  key: string;
  label: string;
  color?: string;
  yAxisId?: 'left' | 'right';
}

interface Props {
  title: string;
  timeseries: NormalizedMetric[];
  series: Series[];
  height?: number;
}

const COLORS = ['#001b5e', '#5b9bd5', '#16a34a', '#dc2626', '#f59e0b'];

function buildChartData(timeseries: NormalizedMetric[], series: Series[]): Record<string, unknown>[] {
  const byDate: Record<string, Record<string, unknown>> = {};
  for (const m of timeseries) {
    if (!m.date_bucket) continue;
    if (!byDate[m.date_bucket]) byDate[m.date_bucket] = { date: m.date_bucket };
    if (series.some(s => s.key === m.metric_key)) {
      byDate[m.date_bucket][m.metric_key] = m.value;
    }
  }
  return Object.values(byDate).sort((a, b) =>
    String(a.date) < String(b.date) ? -1 : 1
  );
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export const TrendChart: React.FC<Props> = ({ title, timeseries, series, height = 260 }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const data = buildChartData(timeseries, series);
  const hasDualAxis = series.some(s => s.yAxisId === 'right');

  const downloadPng = async () => {
    if (!chartRef.current) return;
    try {
      const dataUrl = await toPng(chartRef.current, { backgroundColor: '#fff' });
      const a = document.createElement('a');
      a.href = dataUrl;
      a.download = `cosight-${title.toLowerCase().replace(/\s+/g, '-')}.png`;
      a.click();
    } catch (e) {
      console.error('Chart export failed', e);
    }
  };

  return (
    <div className="trend-chart">
      <div className="trend-chart__header">
        <span className="trend-chart__title">{title}</span>
        <button className="trend-chart__download" onClick={downloadPng} title="Download as PNG">
          ↓ PNG
        </button>
      </div>
      <div ref={chartRef} style={{ width: '100%' }}>
        <ResponsiveContainer width="100%" height={height}>
          <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey="date"
              tickFormatter={formatDate}
              tick={{ fontSize: 11, fill: '#6b7280' }}
            />
            <YAxis
              yAxisId="left"
              tick={{ fontSize: 11, fill: '#6b7280' }}
              width={50}
            />
            {hasDualAxis && (
              <YAxis
                yAxisId="right"
                orientation="right"
                tick={{ fontSize: 11, fill: '#6b7280' }}
                width={50}
              />
            )}
            <Tooltip
              contentStyle={{ fontSize: 12, borderRadius: 6, border: '1px solid #e2e8f0' }}
              labelFormatter={formatDate}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {series.map((s, i) => (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={s.color || COLORS[i % COLORS.length]}
                yAxisId={s.yAxisId || 'left'}
                dot={false}
                strokeWidth={2}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
