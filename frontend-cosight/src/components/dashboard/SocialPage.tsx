import React, { useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMetricsStore } from '../../stores/metricsStore';
import { TrendChart } from './TrendChart';
import { DataTable } from './DataTable';
import { PlatformBreakdown } from './PlatformBreakdown';
import { KPICard } from './KPICard';
import { DashboardPageShell } from './DashboardPageShell';
import { DateRangePicker } from './DateRangePicker';
import { StaleBadge, LoadingSkeleton, EmptyState, ErrorState, ConnectorError } from './ChannelStatus';
import { SOCIAL_PROMPTS } from '../shared/dashboardPrompts';
import { clampSproutRange, sproutLagNote, SPROUT_DATA_LAG_DAYS } from '../../utils/sproutDates';
import {
  kpiInsightContext,
  platformBreakdownContext,
  timeseriesInsightContext,
  tableInsightContext,
} from '../../utils/insightContext';
import { getChannelCsvUrl } from '../../services/api';
import type { DashboardInsightSection, NormalizedMetric, ScopedContext } from '../../types';
import './Page.css';

const PLATFORM_COLORS: Record<string, string> = {
  linkedin_impressions: '#0077b5',
  instagram_impressions: '#e1306c',
  facebook_impressions: '#1877f2',
  x_impressions: '#14171a',
  threads_impressions: '#101010',
  youtube_impressions: '#ff0000',
  tiktok_impressions: '#010101',
};

function buildPlatformSeries(timeseries: NormalizedMetric[]) {
  const keys = [...new Set(timeseries.map(m => m.metric_key))]
    .filter(k => k.endsWith('_impressions') && k.includes('_') && k !== 'impressions');
  return keys.map((key, i) => ({
    key,
    label: key.replace('_impressions', '').replace(/^\w/, c => c.toUpperCase()),
    color: PLATFORM_COLORS[key] || ['#001b5e', '#5b9bd5', '#16a34a', '#dc2626'][i % 4],
  }));
}

function formatPostDate(iso: string): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function kpiScopedContext(metric: NormalizedMetric, dateRange: { start: string; end: string }): ScopedContext {
  return {
    channel: metric.channel,
    metric_key: metric.metric_key,
    label: metric.label || metric.metric_key.replace(/_/g, ' '),
    date_range: `${dateRange.start}/${dateRange.end}`,
    value: metric.value,
    delta: metric.delta_pct,
  };
}

function kpiContinuePrompt(metric: NormalizedMetric, dateRange: { start: string; end: string }): string {
  const label = metric.label || metric.metric_key.replace(/_/g, ' ');
  return `Dig deeper into ${label} for Columbia Business School social (${dateRange.start} to ${dateRange.end}). What drove the change and what should we watch next?`;
}

export const SocialPage: React.FC = () => {
  const { dateRange, setDateRange, social, loading, errors, fetchSocial } = useMetricsStore();
  const navigate = useNavigate();

  useEffect(() => { fetchSocial(); }, [dateRange]);

  useEffect(() => {
    const clamped = clampSproutRange(dateRange);
    if (clamped.start !== dateRange.start || clamped.end !== dateRange.end) {
      setDateRange(clamped);
    }
  }, []);

  const isLoading = loading['social'];
  const error = errors['social'];
  const handleDrillIn = useCallback((ctx: ScopedContext) =>
    navigate('/chat', { state: { scopedContext: ctx, dateRange } }),
  [navigate, dateRange]);

  const isPending = error?.includes('pending credential');
  const metricsReady = !isLoading && !!social;

  const overallSummary = useMemo(
    () => social?.summary.filter(m => !m.dimension) ?? [],
    [social],
  );

  const platformMetrics = useMemo(
    () => social?.summary.filter(m => m.dimension) ?? [],
    [social],
  );

  const platformSeries = useMemo(
    () => (social ? buildPlatformSeries(social.timeseries) : []),
    [social],
  );

  const topPostRows = useMemo(
    () => (social?.top_posts ?? []).map(p => ({
      platform: p.platform,
      profile: p.profile_name,
      post: p.text,
      date: formatPostDate(p.created_time),
      impressions: Math.round(p.impressions),
      engagements: Math.round(p.engagements),
      link: p.permalink ?? '',
    })),
    [social],
  );

  const socialTimeseries = social?.timeseries ?? [];

  const insightSections = useMemo((): DashboardInsightSection[] => {
    if (!social) return [];
    const sections: DashboardInsightSection[] = [];
    const dr = `${dateRange.start} to ${dateRange.end}`;

    // ── All KPI cards as a single split section ──────────────────────────
    if (overallSummary.length > 0) {
      // Derive engagement rate (engagements / impressions × 100) as a 6th card
      // so the 3×2 grid is always full. Only add if both source metrics exist.
      const impressionsMetric = overallSummary.find(m => m.metric_key === 'impressions');
      const engagementsMetric = overallSummary.find(m => m.metric_key === 'engagements');
      const engRateMetric: NormalizedMetric | null =
        impressionsMetric && engagementsMetric && impressionsMetric.value > 0
          ? {
              channel: 'social',
              metric_key: 'engagement_rate',
              label: 'Engagement Rate',
              value: (engagementsMetric.value / impressionsMetric.value) * 100,
              prior_value:
                impressionsMetric.prior_value && engagementsMetric.prior_value && impressionsMetric.prior_value > 0
                  ? (engagementsMetric.prior_value / impressionsMetric.prior_value) * 100
                  : undefined,
              delta_pct:
                impressionsMetric.prior_value && engagementsMetric.prior_value && impressionsMetric.prior_value > 0
                  ? (() => {
                      const cur = (engagementsMetric.value / impressionsMetric.value) * 100;
                      const prev = (engagementsMetric.prior_value! / impressionsMetric.prior_value!) * 100;
                      return prev > 0 ? ((cur - prev) / prev) * 100 : undefined;
                    })()
                  : undefined,
              unit: 'percent',
            }
          : null;

      const displayKpis = engRateMetric
        ? [...overallSummary, engRateMetric]
        : overallSummary;

      sections.push({
        id: 'kpi-overview',
        layout: 'split',
        content: (
          <div className="kpi-grid">
            {displayKpis.map(metric => (
              <KPICard
                key={metric.metric_key}
                metric={metric}
                dateRange={dateRange}
                onDrillIn={handleDrillIn}
              />
            ))}
          </div>
        ),
        // Aggregate context covering all KPIs for the AI annotation
        context: {
          section: 'kpi_overview',
          channel: 'social',
          date_range: dr,
          metrics: overallSummary.map(m => ({
            key: m.metric_key,
            label: m.label ?? m.metric_key.replace(/_/g, ' '),
            value: m.value,
            delta_pct: m.delta_pct,
            unit: m.unit,
          })),
        },
        continuePrompt: `Dig deeper into CBS social performance metrics for ${dr}. What drove the changes across impressions, engagements, reach, and followers?`,
        scopedContext: {
          channel: 'social',
          metric_key: 'kpi_overview',
          label: 'Social KPIs',
          date_range: `${dateRange.start}/${dateRange.end}`,
        },
      });
    }

    if (platformMetrics.length > 0) {
      sections.push({
        id: 'platform-breakdown',
        content: <PlatformBreakdown metrics={platformMetrics} />,
        context: platformBreakdownContext(platformMetrics),
        continuePrompt: `Compare CBS social platform performance (${dr}). Which networks drove impressions and engagements, and where should we focus next?`,
        scopedContext: { channel: 'social', metric_key: 'platform_breakdown', label: 'By Platform', date_range: `${dateRange.start}/${dateRange.end}` },
      });
    }

    if (socialTimeseries.length > 0) {
      const impEngSeries = [
        { key: 'impressions', label: 'Impressions' },
        { key: 'engagements', label: 'Engagements' },
      ];
      sections.push({
        id: 'impressions-engagements',
        content: (
          <TrendChart
            title="Impressions & Engagements"
            timeseries={socialTimeseries}
            series={[
              { key: 'impressions', label: 'Impressions', color: '#001b5e' },
              { key: 'engagements', label: 'Engagements', color: '#5b9bd5', yAxisId: 'right' },
            ]}
          />
        ),
        context: timeseriesInsightContext('Impressions & Engagements', socialTimeseries, impEngSeries),
        continuePrompt: `Explain the impressions and engagements trend for CBS social (${dr}). Were there spikes, drop-offs, or divergence between the two metrics?`,
        scopedContext: { channel: 'social', metric_key: 'impressions_engagements', label: 'Impressions & Engagements', date_range: `${dateRange.start}/${dateRange.end}` },
      });

      if (platformSeries.length > 0) {
        sections.push({
          id: 'impressions-by-platform',
          content: (
            <TrendChart
              title="Impressions by Platform"
              timeseries={socialTimeseries}
              series={platformSeries}
            />
          ),
          context: timeseriesInsightContext(
            'Impressions by Platform',
            socialTimeseries,
            platformSeries.map(s => ({ key: s.key, label: s.label })),
          ),
          continuePrompt: `Break down impressions by platform for CBS social (${dr}). Which channels gained or lost share over time?`,
          scopedContext: { channel: 'social', metric_key: 'impressions_by_platform', label: 'Impressions by Platform', date_range: `${dateRange.start}/${dateRange.end}` },
        });
      }

      sections.push({
        id: 'followers-gained',
        content: (
          <TrendChart
            title="Followers Gained"
            timeseries={socialTimeseries}
            series={[
              { key: 'followers_gained', label: 'Followers Gained', color: '#16a34a' },
            ]}
          />
        ),
        context: timeseriesInsightContext('Followers Gained', socialTimeseries, [
          { key: 'followers_gained', label: 'Followers Gained' },
        ]),
        continuePrompt: `Analyze followers gained for CBS social (${dr}). When did growth accelerate or slow, and what might explain it?`,
        scopedContext: { channel: 'social', metric_key: 'followers_gained', label: 'Followers Gained', date_range: `${dateRange.start}/${dateRange.end}` },
      });
    }

    if (topPostRows.length > 0) {
      const top = social.top_posts?.[0];
      sections.push({
        id: 'top-posts',
        content: (
          <DataTable
            title="Top Posts"
            headers={['platform', 'profile', 'post', 'date', 'impressions', 'engagements', 'link']}
            rows={topPostRows}
          />
        ),
        context: tableInsightContext(
          'Top Posts',
          topPostRows.length,
          top ? `${top.platform} post with ${Math.round(top.impressions).toLocaleString()} impressions` : undefined,
        ),
        continuePrompt: `What patterns do you see in our top CBS social posts (${dr})? What made the leading posts work?`,
        scopedContext: { channel: 'social', metric_key: 'top_posts', label: 'Top Posts', date_range: `${dateRange.start}/${dateRange.end}` },
      });
    }

    return sections;
  }, [social, overallSummary, platformMetrics, platformSeries, socialTimeseries, topPostRows, dateRange, handleDrillIn]);

  const header = (
    <div className="cs-page__header">
      <h1>Social Media</h1>
      <span className="cs-page__scope">Columbia Business School</span>
      {social && <StaleBadge status={social.status} channel="social" message={social.error_message} />}
      <DateRangePicker value={dateRange} onChange={setDateRange} endLagDays={SPROUT_DATA_LAG_DAYS} />
    </div>
  );

  return (
    <DashboardPageShell
      channel="social"
      dateRange={dateRange}
      briefNote={metricsReady && social ? sproutLagNote(social.end_date) : undefined}
      metricsReady={metricsReady}
      insightSections={insightSections}
      header={(
        <>
          {header}
          {isLoading && <LoadingSkeleton rows={2} />}
          {!isLoading && isPending && (
            <div className="pending-notice">
              <span>🔑</span>
              <div>
                <strong>Sprout Social connection pending</strong>
                <p>The Sprout API token has not yet been configured.</p>
              </div>
            </div>
          )}
          {!isLoading && error && !isPending && <ErrorState message={error} />}
          {!isLoading && !error && social?.status === 'error' && (
            <ConnectorError channel="Social" message={social.error_message} />
          )}
          {!isLoading && !error && !social && <EmptyState />}
        </>
      )}
      quickPrompts={SOCIAL_PROMPTS}
      inputPlaceholder="Ask CoSight about CBS social performance…"
    >
      <div style={{ marginTop: 16 }}>
        <a className="csv-link" href={getChannelCsvUrl('social', dateRange)} download>
          ↓ Download CSV
        </a>
      </div>
    </DashboardPageShell>
  );
};
