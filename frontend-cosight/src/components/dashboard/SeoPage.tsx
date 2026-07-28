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

export const SeoPage: React.FC = () => {
  const { dateRange, setDateRange, seo, loading, errors, fetchSeo } = useMetricsStore();
  const navigate = useNavigate();

  useEffect(() => { fetchSeo(); }, [dateRange]);

  const isLoading = loading['seo'];
  const error = errors['seo'];
  const handleDrillIn = (ctx: ScopedContext) =>
    navigate('/chat', { state: { scopedContext: ctx, dateRange } });

  const topQueries = seo?.summary
    .filter(m => m.metric_key === 'query_clicks' && m.dimension)
    .slice(0, 25)
    .map(m => ({ query: m.dimension!, clicks: m.value })) || [];

  return (
    <div className="cs-page">
      <div className="cs-page__header">
        <h1>Search Performance</h1>
        {seo && <StaleBadge status={seo.status} channel="search" message={seo.error_message} />}
        <div style={{ fontSize: 12, color: '#9ca3af' }}>Data via Google Search Console · ~3 day lag</div>
        <DateRangePicker value={dateRange} onChange={setDateRange} />
      </div>

      {isLoading && <LoadingSkeleton rows={4} />}
      {!isLoading && error && <ErrorState message={error} />}
      {!isLoading && !error && !seo && <EmptyState />}

      {!isLoading && seo && (
        <>
          <div className="kpi-grid">
            {seo.summary.filter(m => !m.dimension).map((m, i) => (
              <KPICard key={i} metric={m} dateRange={dateRange} onDrillIn={handleDrillIn} />
            ))}
          </div>

          <TrendChart
            title="Clicks & Impressions"
            timeseries={seo.timeseries}
            series={[
              { key: 'clicks', label: 'Clicks', color: '#001b5e' },
              { key: 'impressions', label: 'Impressions', color: '#5b9bd5', yAxisId: 'right' },
            ]}
          />

          <TrendChart
            title="CTR & Avg Position"
            timeseries={seo.timeseries}
            series={[
              { key: 'ctr', label: 'CTR %', color: '#16a34a' },
              { key: 'avg_position', label: 'Avg Position', color: '#f59e0b', yAxisId: 'right' },
            ]}
          />

          {topQueries.length > 0 && (
            <DataTable
              title="Top Search Queries"
              headers={['query', 'clicks']}
              rows={topQueries}
              csvUrl={getChannelCsvUrl('seo', dateRange)}
            />
          )}
          <AgentInputBar navigateOnSend />
        </>
      )}
    </div>
  );
};
