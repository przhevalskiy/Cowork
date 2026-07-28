/**
 * ReportArtifact renderer — renders a ReportArtifact with export menu.
 * Used on the Reports page AND inline in chat (same component, different contexts).
 * Invariant: all numbers come from the artifact passed in — no re-fetch.
 */
import React, { useState } from 'react';
import type { ReportArtifact as ReportArtifactType } from '../../types';
import { KPICard } from '../dashboard/KPICard';
import { DataTable } from '../dashboard/DataTable';
import { getReportExportUrl } from '../../services/api';
import './ReportArtifact.css';

interface Props {
  artifact: ReportArtifactType;
  compact?: boolean;   // true when rendered inline in chat
}

export const ReportArtifact: React.FC<Props> = ({ artifact, compact }) => {
  const [expanded, setExpanded] = useState(!compact);

  const handleExport = (format: 'slides' | 'csv') => {
    if (!artifact.id) return;
    const url = getReportExportUrl(artifact.id, format);
    window.open(url, '_blank');
  };

  return (
    <div className={`report-artifact ${compact ? 'report-artifact--compact' : ''}`}>
      <div className="ra-header" onClick={() => compact && setExpanded(v => !v)}>
        <div className="ra-title-block">
          <span className="ra-icon">📊</span>
          <div>
            <div className="ra-title">{artifact.title}</div>
            <div className="ra-meta">{artifact.date_range_start} → {artifact.date_range_end}</div>
          </div>
        </div>
        <div className="ra-actions">
          {artifact.id && (
            <>
              <button className="ra-export-btn" onClick={() => handleExport('slides')}>
                ↓ Slides
              </button>
              <button className="ra-export-btn" onClick={() => handleExport('csv')}>
                ↓ CSV
              </button>
            </>
          )}
          {compact && (
            <button className="ra-toggle">{expanded ? '▲' : '▼'}</button>
          )}
        </div>
      </div>

      {expanded && (
        <div className="ra-body">
          {artifact.executive_summary && (
            <div className="ra-summary">
              <strong>Executive Summary</strong>
              <p>{artifact.executive_summary}</p>
            </div>
          )}

          {artifact.sections.map(section => (
            <div key={section.id} className="ra-section">
              <h3 className="ra-section-title">{section.title}</h3>

              {section.kpis.length > 0 && (
                <div className="ra-kpi-row">
                  {section.kpis.slice(0, 6).map((m, i) => (
                    <KPICard key={i} metric={m} />
                  ))}
                </div>
              )}

              {section.narrative && (
                <p className="ra-narrative">{section.narrative}</p>
              )}

              {section.table_rows.length > 0 && (
                <DataTable
                  headers={section.table_headers}
                  rows={section.table_rows as Record<string, unknown>[]}
                  title={section.title}
                />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
