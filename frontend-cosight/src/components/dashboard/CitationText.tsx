/**
 * CitationText — renders brief prose with clickable [1] citation markers.
 */
import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import type { BriefCitation } from '../../types';
import './CitationText.css';

interface Props {
  text: string;
  citations: BriefCitation[];
  isStreaming?: boolean;
}

export const CitationText: React.FC<Props> = ({ text, citations, isStreaming }) => {
  const [activeId, setActiveId] = useState<number | null>(null);
  const [popoverStyle, setPopoverStyle] = useState<React.CSSProperties>({});
  const anchorRef = useRef<HTMLElement | null>(null);

  const citationMap = new Map(citations.map(c => [c.id, c]));

  useEffect(() => {
    if (activeId === null) return;
    const handler = (e: MouseEvent) => {
      const t = e.target as HTMLElement;
      if (!t.closest('.citation-popover') && !t.closest('.citation-chip')) {
        setActiveId(null);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [activeId]);

  const openPopover = (id: number, el: HTMLElement) => {
    anchorRef.current = el;
    const rect = el.getBoundingClientRect();
    setPopoverStyle({
      position: 'fixed',
      top: rect.bottom + 6,
      left: Math.min(rect.left, window.innerWidth - 320),
      zIndex: 9999,
    });
    setActiveId(id);
  };

  const parts = text.split(/(\[\d+\])/g);
  const active = activeId !== null ? citationMap.get(activeId) : null;

  return (
    <>
      <p className="citation-text">
        {parts.map((part, i) => {
          const match = part.match(/^\[(\d+)\]$/);
          if (match) {
            const id = parseInt(match[1], 10);
            const cite = citationMap.get(id);
            if (!cite) return part;
            if (isStreaming) {
              return (
                <sup key={i} className="citation-chip citation-chip--pending">
                  {id}
                </sup>
              );
            }
            return (
              <button
                key={i}
                type="button"
                className="citation-chip"
                onClick={e => openPopover(id, e.currentTarget)}
                title={`${cite.label}: ${cite.formatted_value} (${cite.source})`}
              >
                {id}
              </button>
            );
          }
          return <span key={i}>{part}</span>;
        })}
        {isStreaming && <span className="citation-text__cursor" />}
      </p>

      {active && createPortal(
        <div className="citation-popover" style={popoverStyle}>
          <div className="citation-popover__source">{active.source}</div>
          <div className="citation-popover__label">{active.label}</div>
          <div className="citation-popover__value">{active.formatted_value}</div>
          {active.delta_pct != null && (
            <div className={`citation-popover__delta ${active.delta_pct >= 0 ? 'up' : 'down'}`}>
              {active.delta_pct >= 0 ? '↑' : '↓'} {Math.abs(active.delta_pct).toFixed(1)}% vs prior period
            </div>
          )}
          <div className="citation-popover__range">{active.date_range}</div>
          <div className="citation-popover__detail">{active.detail}</div>
        </div>,
        document.body,
      )}
    </>
  );
};
