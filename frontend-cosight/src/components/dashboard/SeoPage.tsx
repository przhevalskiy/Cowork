import React, { useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMetricsStore } from '../../stores/metricsStore';
import { KPICard } from './KPICard';
import { TrendChart } from './TrendChart';
import { DataTable } from './DataTable';
import { DashboardPageShell } from './DashboardPageShell';
import { DateRangePicker } from './DateRangePicker';
import { StaleBadge, LoadingSkeleton, EmptyState, ErrorState, ConnectorError } from './ChannelStatus';
import { SEO_PROMPTS } from '../shared/dashboardPrompts';
import { getChannelCsvUrl } from '../../services/api';
import {
  timeseriesInsightContext,
  tableInsightContext,
} from '../../utils/insightContext';
import type { DashboardInsightSection, ScopedContext } from '../../types';
import './Page.css';

export const SeoPage: React.FC = () => {
  const { dateRange, setDateRange, seo, loading, errors, fetchSeo } = useMetricsStore();
  const navigate = useNavigate();

  useEffect(() => { fetchSeo(); }, [dateRange]);

  const isLoading = loading['seo'];
  const error = errors['seo'];
  const handleDrillIn = useCallback(
    (ctx: ScopedContext) => navigate('/chat', { state: { scopedContext: ctx, dateRange } }),
    [navigate, dateRange],
  );

  const summaryKpis = useMemo(() => seo?.summary.filter(m => !m.dimension) ?? [], [seo]);
  const topQueries = useMemo(
    () => (seo?.summary ?? [])
      .filter(m => m.metric_key === 'query_clicks' && m.dimension)
      .slice(0, 25)
      .map(m => ({ query: m.dimension!, clicks: m.value })),
    [seo],
  );

  const insightSections = useMemo((): DashboardInsightSection[] => {
    if (!seo) return [];
    const sections: DashboardInsightSection[] = [];
    const dr = `${dateRange.start} to ${dateRange.end}`;

    // ── KPI grid — split layout ──────────────────────────────────────────
    if (summaryKpis.length > 0) {
      sections.push({
        id: 'kpi-overview',
        layout: 'split',
        content: (
          <div className="kpi-grid">
            {summaryKpis.map(metric => (
              <KPICard
                key={metric.metric_key}
                metric={metric}
                dateRange={dateRange}
                onDrillIn={handleDrillIn}
              />
            ))}
          </div>
        ),
        context: {
          section: 'kpi_overview',
          channel: 'search',
          date_range: dr,
          metrics: summaryKpis.map(m => ({
            key: m.metric_key,
            label: m.label ?? m.metric_key.replace(/_/g, ' '),
            value: m.value,
            delta_pct: m.delta_pct,
            unit: m.unit,
          })),
        },
        continuePrompt: `Dig deeper into CBS search performance for ${dr}. What drove changes in clicks, impressions, CTR, and average position?`,
        scopedContext: {
          channel: 'search',
          metric_key: 'kpi_overview',
          label: 'Search KPIs',
          date_range: `${dateRange.start}/${dateRange.end}`,
        },
      });
    }

    // ── Clicks & Impressions trend — stacked ─────────────────────────────
    if (seo.timeseries.length > 0) {
      sections.push({
        id: 'clicks-impressions',
        content: (
          <TrendChart
            title="Clicks & Impressions"
            timeseries={seo.timeseries}
            series={[
              { key: 'clicks', label: 'Clicks', color: '#001b5e' },
              { key: 'impressions', label: 'Impressions', color: '#5b9bd5', yAxisId: 'right' },
            ]}
          />
        ),
        context: timeseriesInsightContext('Clicks & Impressions', seo.timeseries, [
          { key: 'clicks', label: 'Clicks' },
          { key: 'impressions', label: 'Impressions' },
        ]),
        continuePrompt: `Explain the clicks and impressions trend for CBS search (${dr}). Any notable shifts or divergence?`,
        scopedContext: {
          channel: 'search',
          metric_key: 'clicks_impressions',
          label: 'Clicks & Impressions',
          date_range: `${dateRange.start}/${dateRange.end}`,
        },
      });

      sections.push({
        id: 'ctr-position',
        content: (
          <TrendChart
            title="CTR & Avg Position"
            timeseries={seo.timeseries}
            series={[
              { key: 'ctr', label: 'CTR %', color: '#16a34a' },
              { key: 'avg_position', label: 'Avg Position', color: '#f59e0b', yAxisId: 'right' },
            ]}
          />
        ),
        context: timeseriesInsightContext('CTR & Avg Position', seo.timeseries, [
          { key: 'ctr', label: 'CTR' },
          { key: 'avg_position', label: 'Avg Position' },
        ]),
        continuePrompt: `Analyze the CTR and average position trend for CBS search (${dr}). What's improving and what needs attention?`,
        scopedContext: {
          channel: 'search',
          metric_key: 'ctr_position',
          label: 'CTR & Avg Position',
          date_range: `${dateRange.start}/${dateRange.end}`,
        },
      });
    }

    // ── Top Queries — stacked ────────────────────────────────────────────
    if (topQueries.length > 0) {
      sections.push({
        id: 'top-queries',
        content: (
          <DataTable
            title="Top Search Queries"
            headers={['query', 'clicks']}
            rows={topQueries}
            csvUrl={getChannelCsvUrl('seo', dateRange)}
          />
        ),
        context: tableInsightContext('Top Search Queries', topQueries.length, undefined),
        continuePrompt: `What patterns stand out in the top CBS search queries for ${dr}? Which gained or lost the most traction?`,
        scopedContext: {
          channel: 'search',
          metric_key: 'top_queries',
          label: 'Top Search Queries',
          date_range: `${dateRange.start}/${dateRange.end}`,
        },
      });
    }

    return sections;
  }, [seo, summaryKpis, topQueries, dateRange, handleDrillIn]);

  const metricsReady = !isLoading && !!seo;

  return (
    <DashboardPageShell
      channel="search"
      dateRange={dateRange}
      briefNote={seo?.status === 'ok' ? 'Search Console data typically lags by ~3 days.' : undefined}
      metricsReady={metricsReady}
      insightSections={insightSections}
      header={(
        <>
          <div className="cs-page__header">
            <h1>Search Performance</h1>
            <span className="cs-page__scope">Columbia Business School</span>
            {seo && <StaleBadge status={seo.status} channel="search" message={seo.error_message} />}
            <div style={{ fontSize: 12, color: '#9ca3af' }}>via Google Search Console · ~3 day lag</div>
            <DateRangePicker value={dateRange} onChange={setDateRange} />
          </div>
          {isLoading && <LoadingSkeleton rows={2} />}
          {!isLoading && error && <ErrorState message={error} />}
          {!isLoading && !error && seo?.status === 'error' && (
            <ConnectorError channel="Search" message={seo.error_message} />
          )}
          {!isLoading && !error && !seo && <EmptyState />}
        </>
      )}
      quickPrompts={SEO_PROMPTS}
      inputPlaceholder="Ask CoSight about search queries and rankings…"
    />
  );
};
