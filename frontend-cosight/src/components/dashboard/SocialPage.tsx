import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMetricsStore } from '../../stores/metricsStore';
import { KPICard } from './KPICard';
import { DateRangePicker } from './DateRangePicker';
import { StaleBadge, LoadingSkeleton, EmptyState, ErrorState } from './ChannelStatus';
import { AgentInputBar } from '../shared/AgentInputBar';
import type { ScopedContext } from '../../types';
import './Page.css';

export const SocialPage: React.FC = () => {
  const { dateRange, setDateRange, social, loading, errors, fetchSocial } = useMetricsStore();
  const navigate = useNavigate();

  useEffect(() => { fetchSocial(); }, [dateRange]);

  const isLoading = loading['social'];
  const error = errors['social'];
  const handleDrillIn = (ctx: ScopedContext) =>
    navigate('/chat', { state: { scopedContext: ctx, dateRange } });

  const isPending = error?.includes('pending credential');

  return (
    <div className="cs-page">
      <div className="cs-page__header">
        <h1>Social Media</h1>
        {social && <StaleBadge status={social.status} channel="social" message={social.error_message} />}
        <DateRangePicker value={dateRange} onChange={setDateRange} />
      </div>

      {isLoading && <LoadingSkeleton rows={4} />}
      {!isLoading && isPending && (
        <div className="pending-notice">
          <span>🔑</span>
          <div>
            <strong>Sprout Social connection pending</strong>
            <p>The Sprout API token has not yet been configured. Social metrics will appear here once the credential is added.</p>
          </div>
        </div>
      )}
      {!isLoading && error && !isPending && <ErrorState message={error} />}
      {!isLoading && !error && !social && <EmptyState />}

      {!isLoading && social && social.status === 'ok' && (
        <div className="kpi-grid">
          {social.summary.map((m, i) => (
            <KPICard key={i} metric={m} dateRange={dateRange} onDrillIn={handleDrillIn} />
          ))}
        </div>
      )}
      <AgentInputBar navigateOnSend />
    </div>
  );
};
