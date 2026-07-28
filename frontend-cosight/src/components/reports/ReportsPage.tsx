import React, { useEffect, useState } from 'react';
import { listReports, getReport } from '../../services/api';
import { ReportArtifact } from './ReportArtifact';
import type { ReportArtifact as ReportArtifactType } from '../../types';
import { LoadingSkeleton, EmptyState, ErrorState } from '../dashboard/ChannelStatus';
import './ReportsPage.css';

interface ReportSummary {
  id: string;
  title: string;
  date_range: string;
  created_at: string;
}

export const ReportsPage: React.FC = () => {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeReport, setActiveReport] = useState<ReportArtifactType | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);

  useEffect(() => {
    listReports()
      .then(setReports)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const openReport = async (id: string) => {
    setLoadingReport(true);
    try {
      const artifact = await getReport(id);
      setActiveReport(artifact);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoadingReport(false);
    }
  };

  return (
    <div className="cs-page">
      <div className="cs-page__header">
        <h1>Reports</h1>
      </div>

      {loading && <LoadingSkeleton rows={3} />}
      {!loading && error && <ErrorState message={error} />}
      {!loading && !error && reports.length === 0 && (
        <EmptyState message="No saved reports yet. Use the Overview page or chat to generate one." />
      )}

      <div className="reports-list">
        {reports.map(r => (
          <div
            key={r.id}
            className={`report-row ${activeReport?.id === r.id ? 'report-row--active' : ''}`}
            onClick={() => openReport(r.id)}
          >
            <div className="report-row__icon">📊</div>
            <div className="report-row__info">
              <div className="report-row__title">{r.title}</div>
              <div className="report-row__meta">
                {r.date_range} · {new Date(r.created_at).toLocaleDateString()}
              </div>
            </div>
            <div className="report-row__arrow">›</div>
          </div>
        ))}
      </div>

      {loadingReport && <LoadingSkeleton rows={4} />}

      {activeReport && !loadingReport && (
        <ReportArtifact artifact={activeReport} />
      )}
    </div>
  );
};
