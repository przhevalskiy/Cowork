import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMetricsStore } from '../../stores/metricsStore';
import { KPICard } from './KPICard';
import { TrendChart } from './TrendChart';
import { DateRangePicker } from './DateRangePicker';
import { StaleBadge, LoadingSkeleton, ErrorState } from './ChannelStatus';
import { ChibiAvatars } from '../shared/ChibiAvatars';
import { AgentInputBar } from '../shared/AgentInputBar';
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
  const allSummaryKpis = channels.flatMap(c => c!.summary.filter((m: NormalizedMetric) => !m.date_bucket && !m.dimension));

  const isLoading = loading['overview'];
  const error = errors['overview'];

  return (
    <div className="cs-page">

      {/* ── Always-visible header with chibis ── */}
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

      {/* ── Ask bar — always visible below header ── */}
      <AgentInputBar navigateOnSend />

      {/* ── Data states ── */}
      {isLoading && <LoadingSkeleton rows={4} />}
      {!isLoading && error && <ErrorState message={error} />}

      {!isLoading && allSummaryKpis.length > 0 && (
        <>
          <div className="kpi-grid">
            {allSummaryKpis.slice(0, 8).map((m, i) => (
              <KPICard
                key={`${m.channel}-${m.metric_key}-${i}`}
                metric={m}
                dateRange={dateRange}
                onDrillIn={handleDrillIn}
              />
            ))}
          </div>

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
        </>
      )}
    </div>
  );
};
