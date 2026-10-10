import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMetricsStore } from '../../stores/metricsStore';
import { TrendChart } from './TrendChart';
import { DashboardPageShell } from './DashboardPageShell';
import { DateRangePicker } from './DateRangePicker';
import { StaleBadge, LoadingSkeleton, ErrorState } from './ChannelStatus';
import { ChibiAvatars } from '../shared/ChibiAvatars';
import { OVERVIEW_PROMPTS } from '../shared/dashboardPrompts';
import type { ScopedContext, NormalizedMetric } from '../../types';
import './Page.css';
import './OverviewPage.css';

export const OverviewPage: React.FC = () => {
  const { dateRange, setDateRange, overview, loading, errors, fetchOverview } = useMetricsStore();
  const navigate = useNavigate();

  useEffect(() => { fetchOverview(); }, [dateRange]);

  const handleDrillIn = (ctx: ScopedContext) => {
    navigate('/chat', { state: { scopedContext: ctx, dateRange } });
  };

  const channels = [overview?.web, overview?.search, overview?.email, overview?.social].filter(Boolean);
  const allSummaryKpis = channels.flatMap(c =>
    c!.summary.filter((m: NormalizedMetric) => !m.date_bucket && !m.dimension)
  );

  const isLoading = loading['overview'];
  const error = errors['overview'];

  return (
    <DashboardPageShell
      channel="overview"
      dateRange={dateRange}
      metricsReady={!isLoading && !!overview}
      summaryKpis={allSummaryKpis.slice(0, 8)}
      header={(
        <>
          <div className="overview-header">
            <ChibiAvatars count={5} />
            <div className="overview-header__text">
              <h1>Overview</h1>
              <div className="cs-page__badges">
                {channels.map(c => c && (
                  <StaleBadge key={c.channel} status={c.status} channel={c.channel} message={c.error_message} />
                ))}
              </div>
            </div>
            <DateRangePicker value={dateRange} onChange={setDateRange} />
          </div>
          {isLoading && <LoadingSkeleton rows={2} />}
          {!isLoading && error && <ErrorState message={error} />}
        </>
      )}
      quickPrompts={OVERVIEW_PROMPTS}
      inputPlaceholder="Ask CoSight anything about your marketing data…"
      onDrillIn={handleDrillIn}
    >
      {overview?.web && overview?.search && (
        <TrendChart
          title="Web Sessions vs Search Clicks"
          timeseries={[...(overview.web.timeseries || []), ...(overview.search.timeseries || [])]}
          series={[
            { key: 'sessions', label: 'Sessions', color: '#001b5e' },
            { key: 'clicks', label: 'Search Clicks', color: '#5b9bd5', yAxisId: 'right' },
          ]}
        />
      )}
    </DashboardPageShell>
  );
};
