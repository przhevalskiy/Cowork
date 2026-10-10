/**
 * StreamingBrief — Perplexity-style SSE answer with inline citations.
 */
import React, { useEffect, useRef, useState, useCallback } from 'react';
import { CoSightGlyph } from '../chat/CoSightGlyph';
import { CitationText } from './CitationText';
import { streamBrief } from '../../services/api';
import { useSmoothStream } from '../../hooks/useSmoothStream';
import type { BriefCitation, DateRange } from '../../types';
import './StreamingBrief.css';

interface Props {
  channel: string;
  dateRange: DateRange;
  note?: string;
  metricsReady?: boolean;
  onComplete?: () => void;
}

export const StreamingBrief: React.FC<Props> = ({
  channel,
  dateRange,
  note,
  metricsReady = true,
  onComplete,
}) => {
  const [citations, setCitations] = useState<BriefCitation[]>([]);
  const [phase, setPhase] = useState<'idle' | 'streaming' | 'done' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  const handleDrain = useCallback(() => {
    setPhase('done');
    onCompleteRef.current?.();
  }, []);

  const { text, append, finish, reset } = useSmoothStream(handleDrain);

  useEffect(() => {
    if (!metricsReady) return;

    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;

    setCitations([]);
    reset();
    setError(null);
    setPhase('streaming');

    streamBrief({
      channel,
      dateRange,
      note,
      signal: ac.signal,
      onCitations: setCitations,
      onChunk: append,
      onDone: finish,
      onError: msg => {
        setError(msg);
        setPhase('error');
        onCompleteRef.current?.();
      },
    }).catch(e => {
      if (ac.signal.aborted) return;
      setError((e as Error).message);
      setPhase('error');
      onCompleteRef.current?.();
    });

    return () => ac.abort();
  }, [channel, dateRange.start, dateRange.end, note, metricsReady, append, finish, reset]);

  const isStreaming = phase === 'streaming';

  if (!metricsReady) {
    return (
      <div className="streaming-brief streaming-brief--loading">
        <CoSightGlyph state="loading" size={24} />
        <span>Loading metrics…</span>
      </div>
    );
  }

  if (phase === 'error') {
    return (
      <div className="streaming-brief streaming-brief--error">
        <CoSightGlyph state="idle" size={24} />
        <span>{error || 'Brief unavailable'}</span>
      </div>
    );
  }

  return (
    <div className="streaming-brief">
      <div className="streaming-brief__avatar">
        <CoSightGlyph state={isStreaming ? 'loading' : 'done'} size={24} />
      </div>
      <div className="streaming-brief__message">
        {text ? (
          <CitationText text={text} citations={citations} isStreaming={isStreaming} />
        ) : (
          <p className="streaming-brief__placeholder">CoSight is analyzing your data…</p>
        )}
        {note && phase === 'done' && (
          <p className="streaming-brief__note">{note}</p>
        )}
      </div>
    </div>
  );
};
