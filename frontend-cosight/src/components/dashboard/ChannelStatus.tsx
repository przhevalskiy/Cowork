/**
 * Stale/error badge shown per channel when a connector returns non-ok status.
 * Loading skeleton for in-progress fetches.
 */
import React from 'react';
import type { ChannelStatus } from '../../types';
import './ChannelStatus.css';

export const StaleBadge: React.FC<{ status: ChannelStatus; channel: string; message?: string }> = ({ status, channel, message }) => {
  if (status === 'ok') return null;
  return (
    <div className={`channel-badge channel-badge--${status}`} title={message}>
      {channel.toUpperCase()} {status === 'stale' ? '· stale data' : '· unavailable'}
    </div>
  );
};

export const LoadingSkeleton: React.FC<{ rows?: number }> = ({ rows = 3 }) => (
  <div className="loading-skeleton">
    {Array.from({ length: rows }).map((_, i) => (
      <div key={i} className="skeleton-row" />
    ))}
  </div>
);

export const EmptyState: React.FC<{ message?: string }> = ({ message = 'No data for this date range.' }) => (
  <div className="empty-state">{message}</div>
);

export const ErrorState: React.FC<{ message: string }> = ({ message }) => (
  <div className="error-state">
    <span>⚠</span> {message}
  </div>
);
