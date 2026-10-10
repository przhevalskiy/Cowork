import React, { useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMetricsStore } from '../../stores/metricsStore';
import { KPICard } from './KPICard';
import { TrendChart } from './TrendChart';
import { DataTable } from './DataTable';
import { DashboardPageShell } from './DashboardPageShell';
import { DateRangePicker } from './DateRangePicker';
import { StaleBadge, LoadingSkeleton, EmptyState, ErrorState, ConnectorError } from './ChannelStatus';
import { WEB_PROMPTS } from '../shared/dashboardPrompts';
import { getChannelCsvUrl } from '../../services/api';
import {
  timeseriesInsightContext,
  tableInsightContext,
} from '../../utils/insightContext';
import type { DashboardInsightSection, ScopedContext } from '../../types';
import './Page.css';

export const WebPage: React.FC = () => {
  const { dateRange, setDateRange, web, loading, errors, fetchWeb } = useMetricsStore();
  const navigate = useNavigate();

  useEffect(() => { fetchWeb(); }, [dateRange]);

  const isLoading = loading['web'];
  const error = errors['web'];
  const handleDrillIn = useCallback(
    (ctx: ScopedContext) => navigate('/chat', { state: { scopedContext: ctx, dateRange } }),
    [navigate, dateRange],
  );

  const summaryKpis = web?.summary.filter(m => !m.dimension) ?? [];
  const topPages = useMemo(
    () => (web?.summary ?? [])
      .filter(m => m.metric_key === 'sessions' && m.dimension)
      .slice(0, 20)
      .map(m => ({ page: m.dimension!, sessions: m.value })),
    [web],
  );

  const insightSections = useMemo((): DashboardInsightSection[] => {
    if (!web) return [];
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
          channel: 'web',
          date_range: dr,
          metrics: summaryKpis.map(m => ({
            key: m.metric_key,
            label: m.label ?? m.metric_key.replace(/_/g, ' '),
            value: m.value,
            delta_pct: m.delta_pct,
            unit: m.unit,
          })),
        },
        continuePrompt: `Dig deeper into CBS web analytics for ${dr}. What drove the changes across sessions, users, and engagement?`,
        scopedContext: {
          channel: 'web',
          metric_key: 'kpi_overview',
          label: 'Web KPIs',
          date_range: `${dateRange.start}/${dateRange.end}`,
        },
      });
    }

    // ── Sessions & Active Users trend — stacked ──────────────────────────
    if (web.timeseries.length > 0) {
      const tsSeries = [
        { key: 'sessions', label: 'Sessions' },
        { key: 'active_users', label: 'Active Users' },
      ];
      sections.push({
        id: 'sessions-trend',
        content: (
          <TrendChart
            title="Sessions & Active Users"
            timeseries={web.timeseries}
            series={[
              { key: 'sessions', label: 'Sessions', color: '#001b5e' },
              { key: 'active_users', label: 'Active Users', color: '#5b9bd5' },
            ]}
          />
        ),
        context: timeseriesInsightContext('Sessions & Active Users', web.timeseries, tsSeries),
        continuePrompt: `Explain the sessions and active users trend for CBS web (${dr}). Any spikes, drops, or divergence?`,
        scopedContext: {
          channel: 'web',
          metric_key: 'sessions_trend',
          label: 'Sessions & Active Users',
          date_range: `${dateRange.start}/${dateRange.end}`,
        },
      });
    }

    // ── Top Pages — stacked ──────────────────────────────────────────────
    if (topPages.length > 0) {
      sections.push({
        id: 'top-pages',
        content: (
          <DataTable
            title="Top Pages"
            headers={['page', 'sessions']}
            rows={topPages}
            csvUrl={getChannelCsvUrl('web', dateRange)}
          />
        ),
        context: tableInsightContext('Top Pages', topPages.length, undefined),
        continuePrompt: `What patterns stand out in the top CBS web pages for ${dr}? What's working and what needs attention?`,
        scopedContext: {
          channel: 'web',
          metric_key: 'top_pages',
          label: 'Top Pages',
          date_range: `${dateRange.start}/${dateRange.end}`,
        },
      });
    }

    return sections;
  }, [web, summaryKpis, topPages, dateRange, handleDrillIn]);

  const metricsReady = !isLoading && !!web;

  return (
    <DashboardPageShell
      channel="web"
      dateRange={dateRange}
      metricsReady={metricsReady}
      insightSections={insightSections}
      header={(
        <>
          <div className="cs-page__header">
            <h1>Web Analytics</h1>
            <span className="cs-page__scope">Columbia Business School</span>
            {web && <StaleBadge status={web.status} channel="web" message={web.error_message} />}
            <DateRangePicker value={dateRange} onChange={setDateRange} />
          </div>
          {isLoading && <LoadingSkeleton rows={2} />}
          {!isLoading && error && <ErrorState message={error} />}
          {!isLoading && !error && web?.status === 'error' && (
            <ConnectorError channel="Web" message={web.error_message} />
          )}
          {!isLoading && !error && !web && <EmptyState />}
        </>
      )}
      quickPrompts={WEB_PROMPTS}
      inputPlaceholder="Ask CoSight about web traffic and top pages…"
    />
  );
};
