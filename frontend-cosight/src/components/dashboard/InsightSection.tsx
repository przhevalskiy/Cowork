/**
 * InsightSection — one dashboard block with a one-time streamed insight.
 *
 * layout="stacked"  (default) — content full-width, AI text below
 * layout="split"              — content on the left (~60%), AI annotation
 *                               on the right (~40%), top-aligned and sticky
 *                               to the content height on wider viewports.
 */
import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { streamSectionBrief } from '../../services/api';
import { CoSightGlyph } from '../chat/CoSightGlyph';
import { useSmoothStream } from '../../hooks/useSmoothStream';
import type { DashboardInsightSection, DateRange, ScopedContext } from '../../types';
import './InsightSection.css';

interface Props {
  section: DashboardInsightSection;
  channel: string;
  dateRange: DateRange;
  streaming: boolean;
  onStreamComplete?: () => void;
  onContinue?: (prompt: string, scopedContext?: ScopedContext) => void;
}

export const InsightSection: React.FC<Props> = ({
  section,
  channel,
  dateRange,
  streaming,
  onStreamComplete,
  onContinue,
}) => {
  const [phase, setPhase] = useState<'idle' | 'streaming' | 'done' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);
  const generationRef = useRef(0);
  const onCompleteRef = useRef(onStreamComplete);
  onCompleteRef.current = onStreamComplete;

  const layout = section.layout ?? 'stacked';

  const contextKey = useMemo(() => JSON.stringify(section.context), [section.context]);

  const handleDrain = useCallback(() => {
    setPhase('done');
    onCompleteRef.current?.();
  }, []);

  const { text, append, finish, reset } = useSmoothStream(handleDrain);
  const appendRef = useRef(append);
  const finishRef = useRef(finish);
  const resetRef = useRef(reset);
  appendRef.current = append;
  finishRef.current = finish;
  resetRef.current = reset;

  useEffect(() => {
    if (!streaming) return;

    const generation = ++generationRef.current;
    const ac = new AbortController();

    resetRef.current();
    setError(null);
    setPhase('streaming');

    streamSectionBrief({
      channel,
      sectionId: section.id,
      dateRange,
      context: section.context,
      signal: ac.signal,
      onChunk: chunk => {
        if (generation !== generationRef.current) return;
        appendRef.current(chunk);
      },
      onDone: () => {
        if (generation !== generationRef.current) return;
        finishRef.current();
      },
      onError: msg => {
        if (generation !== generationRef.current) return;
        setError(msg);
        setPhase('error');
        onCompleteRef.current?.();
      },
    }).catch(e => {
      if (ac.signal.aborted || generation !== generationRef.current) return;
      setError((e as Error).message);
      setPhase('error');
      onCompleteRef.current?.();
    });

    return () => ac.abort();
  }, [streaming, channel, section.id, dateRange.start, dateRange.end, contextKey]);

  const showInsight = streaming || phase !== 'idle';

  // ── Annotation panel (shared between layouts) ───────────────────────────
  const annotationPanel = showInsight ? (
    <div className="insight-section__annotation">
      <div className="insight-section__annotation-header">
        <CoSightGlyph state={phase === 'streaming' ? 'loading' : 'done'} size={16} />
        <span className="insight-section__annotation-label">Analysis</span>
      </div>
      {phase === 'error' ? (
        <p className="insight-section__error">{error || 'Insight unavailable'}</p>
      ) : text ? (
        <p className="insight-section__text">
          {text}
          {phase === 'streaming' && <span className="insight-section__cursor" />}
        </p>
      ) : (
        <p className="insight-section__placeholder">Analyzing…</p>
      )}
      {(phase === 'done' || phase === 'error') && onContinue && (
        <button
          type="button"
          className="insight-section__continue"
          onClick={() => onContinue(section.continuePrompt, section.scopedContext)}
        >
          Continue in chat ✦
        </button>
      )}
    </div>
  ) : null;

  // ── Split layout ─────────────────────────────────────────────────────────
  if (layout === 'split') {
    return (
      <div className="insight-section insight-section--split">
        <div className="insight-section__split-left">
          {/* Always reserve space so the left column doesn't collapse before streaming */}
          {showInsight
            ? annotationPanel
            : (
              <div className="insight-section__annotation insight-section__annotation--waiting">
                <div className="insight-section__annotation-header">
                  <CoSightGlyph state="idle" size={16} />
                  <span className="insight-section__annotation-label">Analysis</span>
                </div>
                <p className="insight-section__placeholder">Preparing analysis…</p>
              </div>
            )
          }
        </div>
        <div className="insight-section__split-right">
          {section.content}
        </div>
      </div>
    );
  }

  // ── Stacked layout (default) ─────────────────────────────────────────────
  return (
    <div className="insight-section insight-section--stacked">
      <div className="insight-section__content">
        {section.content}
      </div>
      {showInsight && (
        <div className="insight-section__insight">
          {phase === 'error' ? (
            <p className="insight-section__error">{error || 'Insight unavailable'}</p>
          ) : text ? (
            <p className="insight-section__text">
              {text}
              {phase === 'streaming' && <span className="insight-section__cursor" />}
            </p>
          ) : (
            <p className="insight-section__placeholder">Analyzing this section…</p>
          )}
          {(phase === 'done' || phase === 'error') && onContinue && (
            <button
              type="button"
              className="insight-section__continue"
              onClick={() => onContinue(section.continuePrompt, section.scopedContext)}
            >
              Continue in chat ✦
            </button>
          )}
        </div>
      )}
    </div>
  );
};
