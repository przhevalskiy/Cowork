/**
 * DashboardPageShell — Perplexity-style layout:
 * scrollable brief + sequential insight sections, fixed bottom input bar.
 */
import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { StreamingBrief } from './StreamingBrief';
import { StaggeredKPIGrid } from './StaggeredKPIGrid';
import { SequentialInsightSections } from './SequentialInsightSections';
import { AgentInputBar } from '../shared/AgentInputBar';
import { useChatStore } from '../../stores/chatStore';
import type { DashboardPrompt } from '../shared/dashboardPrompts';
import type { DashboardInsightSection, NormalizedMetric, ScopedContext, DateRange } from '../../types';
import './DashboardPageShell.css';

interface Props {
  channel: string;
  dateRange: DateRange;
  briefNote?: string;
  metricsReady: boolean;
  summaryKpis?: NormalizedMetric[];
  insightSections?: DashboardInsightSection[];
  header: React.ReactNode;
  quickPrompts: DashboardPrompt[];
  inputPlaceholder: string;
  onDrillIn?: (ctx: ScopedContext) => void;
  children?: React.ReactNode;
}

export const DashboardPageShell: React.FC<Props> = ({
  channel,
  dateRange,
  briefNote,
  metricsReady,
  summaryKpis = [],
  insightSections,
  header,
  quickPrompts,
  inputPlaceholder,
  onDrillIn,
  children,
}) => {
  const [briefDone, setBriefDone] = useState(false);
  const [kpisDone, setKpisDone] = useState(false);
  const [sectionsDone, setSectionsDone] = useState(false);
  const navigate = useNavigate();
  const { createDiscussion, setActiveDiscussion } = useChatStore();

  const handleBriefComplete = useCallback(() => setBriefDone(true), []);
  const handleKpisComplete = useCallback(() => setKpisDone(true), []);

  const rangeKey = `${dateRange.start}-${dateRange.end}`;
  React.useEffect(() => {
    setBriefDone(false);
    setKpisDone(false);
    setSectionsDone(false);
  }, [rangeKey]);

  const useInsightSections = insightSections && insightSections.length > 0;
  const showKpiGrid = !useInsightSections && briefDone && metricsReady && summaryKpis.length > 0;

  React.useEffect(() => {
    if (!useInsightSections && briefDone && metricsReady && summaryKpis.length === 0) {
      setKpisDone(true);
    }
  }, [useInsightSections, briefDone, metricsReady, summaryKpis.length]);

  const handleContinueInsight = useCallback(async (prompt: string, scopedContext?: ScopedContext) => {
    const id = await createDiscussion();
    setActiveDiscussion(id);
    navigate('/chat', { state: { seedMessage: prompt, scopedContext, dateRange } });
  }, [createDiscussion, setActiveDiscussion, navigate, dateRange]);

  const showLegacyChildren = !useInsightSections && kpisDone;
  const showInsightChildren = useInsightSections && sectionsDone;

  return (
    <div className="dashboard-shell">
      <div className="dashboard-shell__scroll">
        <div className="dashboard-shell__inner cs-page">
          {header}

          <StreamingBrief
            channel={channel}
            dateRange={dateRange}
            note={briefNote}
            metricsReady={metricsReady}
            onComplete={handleBriefComplete}
          />

          {useInsightSections ? (
            <SequentialInsightSections
              channel={channel}
              dateRange={dateRange}
              sections={insightSections}
              active={briefDone && metricsReady}
              onContinue={handleContinueInsight}
              onAllComplete={() => setSectionsDone(true)}
            />
          ) : (
            <StaggeredKPIGrid
              metrics={summaryKpis}
              visible={showKpiGrid}
              dateRange={dateRange}
              onDrillIn={onDrillIn}
              onComplete={handleKpisComplete}
            />
          )}

          {(showLegacyChildren || showInsightChildren) && children && (
            <div className="dashboard-content-reveal">{children}</div>
          )}
        </div>
      </div>

      <div className="dashboard-shell__input">
        <AgentInputBar
          navigateOnSend
          quickPrompts={quickPrompts}
          placeholder={inputPlaceholder}
        />
      </div>
    </div>
  );
};
