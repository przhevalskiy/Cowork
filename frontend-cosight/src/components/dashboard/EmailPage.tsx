import React, { useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMetricsStore } from '../../stores/metricsStore';
import { KPICard } from './KPICard';
import { DashboardPageShell } from './DashboardPageShell';
import { DateRangePicker } from './DateRangePicker';
import { StaleBadge, LoadingSkeleton, EmptyState, ErrorState, ConnectorError } from './ChannelStatus';
import { EMAIL_PROMPTS } from '../shared/dashboardPrompts';
import { getChannelCsvUrl } from '../../services/api';
import type { DashboardInsightSection, ScopedContext } from '../../types';
import './Page.css';

export const EmailPage: React.FC = () => {
  const { dateRange, setDateRange, email, loading, errors, fetchEmail } = useMetricsStore();
  const navigate = useNavigate();

  useEffect(() => { fetchEmail(); }, [dateRange]);

  const isLoading = loading['email'];
  const error = errors['email'];
  const handleDrillIn = useCallback(
    (ctx: ScopedContext) => navigate('/chat', { state: { scopedContext: ctx, dateRange } }),
    [navigate, dateRange],
  );

  const summaryKpis = useMemo(() => email?.summary ?? [], [email]);

  const insightSections = useMemo((): DashboardInsightSection[] => {
    if (!email) return [];
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
          channel: 'email',
          date_range: dr,
          metrics: summaryKpis.map(m => ({
            key: m.metric_key,
            label: m.label ?? m.metric_key.replace(/_/g, ' '),
            value: m.value,
            delta_pct: m.delta_pct,
            unit: m.unit,
          })),
        },
        continuePrompt: `Dig deeper into CBS email marketing performance for ${dr}. What drove changes in open rate, click rate, and sends?`,
        scopedContext: {
          channel: 'email',
          metric_key: 'kpi_overview',
          label: 'Email KPIs',
          date_range: `${dateRange.start}/${dateRange.end}`,
        },
      });
    }

    return sections;
  }, [email, summaryKpis, dateRange, handleDrillIn]);

  const metricsReady = !isLoading && !!email;

  return (
    <DashboardPageShell
      channel="email"
      dateRange={dateRange}
      metricsReady={metricsReady}
      insightSections={insightSections}
      header={(
        <>
          <div className="cs-page__header">
            <h1>Email Marketing</h1>
            <span className="cs-page__scope">Columbia Business School</span>
            {email && <StaleBadge status={email.status} channel="email" message={email.error_message} />}
            <DateRangePicker value={dateRange} onChange={setDateRange} />
          </div>
          {isLoading && <LoadingSkeleton rows={2} />}
          {!isLoading && error && <ErrorState message={error} />}
          {!isLoading && !error && email?.status === 'error' && (
            <ConnectorError channel="Email" message={email.error_message} />
          )}
          {!isLoading && !error && !email && <EmptyState />}
        </>
      )}
      quickPrompts={EMAIL_PROMPTS}
      inputPlaceholder="Ask CoSight about email campaign performance…"
    >
      {email?.status === 'ok' && (
        <div style={{ marginTop: 16 }}>
          <a className="csv-link" href={getChannelCsvUrl('email', dateRange)} download>
            ↓ Download CSV
          </a>
        </div>
      )}
    </DashboardPageShell>
  );
};
