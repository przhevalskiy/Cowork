/**
 * PlatformBreakdown — compact comparison table for per-platform social KPIs.
 * Replaces a wall of KPI cards with one scannable row per network.
 */
import React, { useMemo, useState } from 'react';
import type { NormalizedMetric } from '../../types';
import { formatCount, formatPercent } from '../../utils/formatNumber';
import './PlatformBreakdown.css';

const PLATFORM_COLORS: Record<string, string> = {
  LinkedIn: '#0077b5',
  Instagram: '#e1306c',
  Facebook: '#1877f2',
  X: '#14171a',
  Threads: '#101010',
  YouTube: '#ff0000',
  TikTok: '#010101',
};

type SortKey = 'platform' | 'impressions' | 'engagements' | 'engagement_rate' | 'followers_count';

interface PlatformRow {
  platform: string;
  color: string;
  impressions: number;
  impressionsDelta?: number;
  engagements: number;
  engagementsDelta?: number;
  engagementRate: number;
  engagementRateDelta?: number;
  followers?: number;
  followersDelta?: number;
  impressionShare: number;
}

interface Props {
  metrics: NormalizedMetric[];
}

function metricByKey(metrics: NormalizedMetric[], key: string): NormalizedMetric | undefined {
  return metrics.find(m => m.metric_key === key);
}

function buildRows(metrics: NormalizedMetric[]): PlatformRow[] {
  const byPlatform = new Map<string, NormalizedMetric[]>();
  for (const m of metrics) {
    if (!m.dimension) continue;
    const list = byPlatform.get(m.dimension) ?? [];
    list.push(m);
    byPlatform.set(m.dimension, list);
  }

  const rows: PlatformRow[] = [];
  for (const [platform, platformMetrics] of byPlatform) {
    const impressions = metricByKey(platformMetrics, 'impressions');
    const engagements = metricByKey(platformMetrics, 'engagements');
    const rate = metricByKey(platformMetrics, 'engagement_rate');
    const followers = metricByKey(platformMetrics, 'followers_count');

    rows.push({
      platform,
      color: PLATFORM_COLORS[platform] ?? '#6b7280',
      impressions: impressions?.value ?? 0,
      impressionsDelta: impressions?.delta_pct,
      engagements: engagements?.value ?? 0,
      engagementsDelta: engagements?.delta_pct,
      engagementRate: rate?.value ?? 0,
      engagementRateDelta: rate?.delta_pct,
      followers: followers?.value,
      followersDelta: followers?.delta_pct,
      impressionShare: 0,
    });
  }

  const totalImpressions = rows.reduce((sum, r) => sum + r.impressions, 0);
  for (const row of rows) {
    row.impressionShare = totalImpressions > 0 ? (row.impressions / totalImpressions) * 100 : 0;
  }

  return rows.sort((a, b) => b.impressions - a.impressions);
}

function DeltaBadge({ delta }: { delta?: number | null }) {
  if (delta === undefined || delta === null) return null;
  const up = delta >= 0;
  return (
    <span className={`platform-breakdown__delta ${up ? 'delta--up' : 'delta--down'}`}>
      {up ? '↑' : '↓'} {Math.abs(delta).toFixed(1)}%
    </span>
  );
}

export const PlatformBreakdown: React.FC<Props> = ({ metrics }) => {
  const [sortKey, setSortKey] = useState<SortKey>('impressions');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const rows = useMemo(() => buildRows(metrics), [metrics]);

  const sorted = useMemo(() => {
    const mult = sortDir === 'asc' ? 1 : -1;
    return [...rows].sort((a, b) => {
      if (sortKey === 'platform') {
        return mult * a.platform.localeCompare(b.platform);
      }
      const av = sortKey === 'engagement_rate'
        ? a.engagementRate
        : sortKey === 'followers_count'
          ? (a.followers ?? -1)
          : a[sortKey];
      const bv = sortKey === 'engagement_rate'
        ? b.engagementRate
        : sortKey === 'followers_count'
          ? (b.followers ?? -1)
          : b[sortKey];
      return mult * ((av as number) - (bv as number));
    });
  }, [rows, sortKey, sortDir]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(d => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const sortIndicator = (key: SortKey) =>
    sortKey === key ? (sortDir === 'asc' ? ' ↑' : ' ↓') : '';

  if (rows.length === 0) return null;

  return (
    <div className="platform-breakdown">
      <div className="platform-breakdown__header">
        <h2 className="platform-breakdown__title">By Platform</h2>
        <span className="platform-breakdown__hint">{rows.length} networks</span>
      </div>
      <div className="platform-breakdown__scroll">
        <table>
          <thead>
            <tr>
              <th onClick={() => handleSort('platform')}>Platform{sortIndicator('platform')}</th>
              <th onClick={() => handleSort('impressions')}>Impressions{sortIndicator('impressions')}</th>
              <th onClick={() => handleSort('engagements')}>Engagements{sortIndicator('engagements')}</th>
              <th onClick={() => handleSort('engagement_rate')}>Eng. Rate{sortIndicator('engagement_rate')}</th>
              <th onClick={() => handleSort('followers_count')}>Followers{sortIndicator('followers_count')}</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(row => (
              <tr key={row.platform}>
                <td>
                  <span className="platform-breakdown__name">
                    <span className="platform-breakdown__dot" style={{ background: row.color }} />
                    {row.platform}
                  </span>
                </td>
                <td>
                  <div className="platform-breakdown__metric-cell">
                    <div className="platform-breakdown__bar-row">
                      <div className="platform-breakdown__bar-track">
                        <div
                          className="platform-breakdown__bar"
                          style={{ width: `${row.impressionShare}%`, background: row.color }}
                          title={`${row.impressionShare.toFixed(1)}% of total impressions`}
                        />
                      </div>
                      <span className="platform-breakdown__value">{formatCount(row.impressions)}</span>
                    </div>
                    <DeltaBadge delta={row.impressionsDelta} />
                  </div>
                </td>
                <td>
                  <div className="platform-breakdown__metric-cell">
                    <span className="platform-breakdown__value">{formatCount(row.engagements)}</span>
                    <DeltaBadge delta={row.engagementsDelta} />
                  </div>
                </td>
                <td>
                  <div className="platform-breakdown__metric-cell">
                    <span className="platform-breakdown__value">{formatPercent(row.engagementRate)}</span>
                    <DeltaBadge delta={row.engagementRateDelta} />
                  </div>
                </td>
                <td>
                  {row.followers !== undefined ? (
                    <div className="platform-breakdown__metric-cell">
                      <span className="platform-breakdown__value">{formatCount(row.followers)}</span>
                      <DeltaBadge delta={row.followersDelta} />
                    </div>
                  ) : (
                    '—'
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
