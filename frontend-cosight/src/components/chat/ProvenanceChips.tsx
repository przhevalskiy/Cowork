/**
 * Provenance chips — data-source badges shown on assistant messages.
 * These are the primary identity marker for the agent. They reflect
 * which tools were actually called, not a static label.
 */
import React from 'react';
import './ProvenanceChips.css';

const TOOL_LABELS: Record<string, { label: string; color: string }> = {
  get_web_metrics:    { label: 'GA4', color: '#e8700a' },
  get_seo_metrics:    { label: 'Search Console', color: '#1a73e8' },
  get_email_metrics:  { label: 'Emma', color: '#6c3591' },
  get_social_metrics: { label: 'Sprout', color: '#6fcf55' },
  generate_report:    { label: 'Report', color: '#001b5e' },
};

interface Props {
  tools: string[];
}

export const ProvenanceChips: React.FC<Props> = ({ tools }) => {
  if (!tools.length) return null;
  return (
    <div className="provenance-chips">
      {tools.map(t => {
        const meta = TOOL_LABELS[t];
        if (!meta) return null;
        return (
          <span
            key={t}
            className="prov-chip"
            style={{ borderColor: meta.color, color: meta.color }}
          >
            {meta.label}
          </span>
        );
      })}
    </div>
  );
};

export const ToolCallIndicator: React.FC<{ tools: string[] }> = ({ tools }) => {
  if (!tools.length) return null;
  const labels = tools.map(t => TOOL_LABELS[t]?.label || t);
  return (
    <div className="tool-indicator">
      <span className="tool-indicator__dot" />
      Querying {labels.join(', ')}…
    </div>
  );
};
