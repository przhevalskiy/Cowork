import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMetricsStore } from '../../stores/metricsStore';
import { KPICard } from './KPICard';
import { DateRangePicker } from './DateRangePicker';
import { StaleBadge, LoadingSkeleton, EmptyState, ErrorState } from './ChannelStatus';
import { AgentInputBar } from '../shared/AgentInputBar';
import { getChannelCsvUrl } from '../../services/api';
import type { ScopedContext } from '../../types';
import './Page.css';

export const EmailPage: React.FC = () => {
  const { dateRange, setDateRange, email, loading, errors, fetchEmail } = useMetricsStore();
  const navigate = useNavigate();

  useEffect(() => { fetchEmail(); }, [dateRange]);

  const isLoading = loading['email'];
  const error = errors['email'];
  const handleDrillIn = (ctx: ScopedContext) =>
    navigate('/chat', { state: { scopedContext: ctx, dateRange } });

  return (
    <div className="cs-page">
      <div className="cs-page__header">
        <h1>Email Marketing</h1>
        {email && <StaleBadge status={email.status} channel="email" message={email.error_message} />}
        <DateRangePicker value={dateRange} onChange={setDateRange} />
      </div>

      {isLoading && <LoadingSkeleton rows={4} />}
      {!isLoading && error && <ErrorState message={error} />}
      {!isLoading && !error && !email && <EmptyState />}

      {!isLoading && email && (
        <>
          <div className="kpi-grid">
            {email.summary.map((m, i) => (
              <KPICard key={i} metric={m} dateRange={dateRange} onDrillIn={handleDrillIn} />
            ))}
          </div>
          <div style={{ marginTop: 16 }}>
            <a className="csv-link" href={getChannelCsvUrl('email', dateRange)} download>
              ↓ Download CSV
            </a>
          </div>
          <AgentInputBar navigateOnSend />
        </>
      )}
    </div>
  );
};
