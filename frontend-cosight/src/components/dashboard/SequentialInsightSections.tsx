/**
 * SequentialInsightSections — reveals dashboard blocks one at a time with
 * streamed insights and a continue-in-chat action per section.
 */
import React, { useState, useEffect } from 'react';
import { InsightSection } from './InsightSection';
import type { DashboardInsightSection, DateRange, ScopedContext } from '../../types';
import './InsightSection.css';

interface Props {
  channel: string;
  dateRange: DateRange;
  sections: DashboardInsightSection[];
  active: boolean;
  onContinue?: (prompt: string, scopedContext?: ScopedContext) => void;
  onAllComplete?: () => void;
}

export const SequentialInsightSections: React.FC<Props> = ({
  channel,
  dateRange,
  sections,
  active,
  onContinue,
  onAllComplete,
}) => {
  const [currentIndex, setCurrentIndex] = useState(0);

  const rangeKey = `${dateRange.start}-${dateRange.end}`;
  useEffect(() => {
    setCurrentIndex(0);
  }, [rangeKey, sections.length]);

  useEffect(() => {
    if (active && currentIndex >= sections.length && sections.length > 0) {
      onAllComplete?.();
    }
  }, [active, currentIndex, sections.length, onAllComplete]);

  if (!active || sections.length === 0) return null;

  return (
    <div className="insight-sections">
      {sections.slice(0, currentIndex + 1).map((section, index) => (
        <InsightSection
          key={`${rangeKey}-${section.id}`}
          section={section}
          channel={channel}
          dateRange={dateRange}
          streaming={index === currentIndex}
          onStreamComplete={() => setCurrentIndex(i => Math.min(i + 1, sections.length))}
          onContinue={onContinue}
        />
      ))}
    </div>
  );
};
