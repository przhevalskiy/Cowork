import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMetricsStore } from '../../stores/metricsStore';
import { KPICard } from './KPICard';
import { TrendChart } from './TrendChart';
import { DataTable } from './DataTable';
import { DateRangePicker } from './DateRangePicker';
import { StaleBadge, LoadingSkeleton, EmptyState, ErrorState } from './ChannelStatus';
import { AgentInputBar } from '../shared/AgentInputBar';
import { getChannelCsvUrl } from '../../services/api';
import type { ScopedContext } from '../../types';
import './Page.css';

export const WebPage: React.FC = () => {
  const { dateRange, setDateRange, web, loading, errors, fetchWeb } = useMetricsStore();
  const navigate = useNavigate();

  useEffect(() => { fetchWeb(); }, [dateRange]);

  const isLoading = loading['web'];
  const error = errors['web'];
  const handleDrillIn = (ctx: ScopedContext) =>
    navigate('/chat', { state: { scopedContext: ctx, dateRange } });

  // Build top-pages table from timeseries dimension data
  const topPages = web?.summary
    .filter(m => m.metric_key === 'sessions' && m.dimension)
    .slice(0, 20)
    .map(m => ({ page: m.dimension!, sessions: m.value })) || [];

  return (
    <div className="cs-page">
      <div className="cs-page__header">
        <h1>Web Analytics</h1>
        {web && <StaleBadge status={web.status} channel="web" message={web.error_message} />}
        <DateRangePicker value={dateRange} onChange={setDateRange} />
      </div>

      {isLoading && <LoadingSkeleton rows={4} />}
      {!isLoading && error && <ErrorState message={error} />}
      {!isLoading && !error && !web && <EmptyState />}

      {!isLoading && web && (
        <>
          <div className="kpi-grid">
            {web.summary.filter(m => !m.dimension).map((m, i) => (
              <KPICard key={i} metric={m} dateRange={dateRange} onDrillIn={handleDrillIn} />
            ))}
          </div>

          <TrendChart
            title="Sessions & Active Users"
            timeseries={web.timeseries}
            series={[
              { key: 'sessions', label: 'Sessions', color: '#001b5e' },
              { key: 'active_users', label: 'Active Users', color: '#5b9bd5' },
            ]}
          />

          {topPages.length > 0 && (
            <DataTable
              title="Top Pages"
              headers={['page', 'sessions']}
              rows={topPages}
              csvUrl={getChannelCsvUrl('web', dateRange)}
            />
          )}
          <AgentInputBar navigateOnSend />
        </>
      )}
    </div>
  );
};
