/**
 * CoSight Chat — agentic conversation interface.
 * - Chibis always visible on empty state (no initialization gate)
 * - Pill input bar matching Cowork's ChatInput exactly
 * - Provenance chips as primary assistant identity
 * - Handles scoped drill-in context and seedMessage from Overview
 */
import React, { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { ArrowUp, Square } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useChatStore } from '../../stores/chatStore';
import { CoSightGlyph } from './CoSightGlyph';
import { ProvenanceChips, ToolCallIndicator } from './ProvenanceChips';
import { ReportArtifact } from '../reports/ReportArtifact';
import { ChibiAvatars } from '../shared/ChibiAvatars';
import type { ScopedContext, DateRange } from '../../types';
import './ChatPage.css';

const QUICK_ACTIONS = [
  'Summarize last 30 days across all channels',
  'What are the top search queries this month?',
  'How is web traffic trending vs last month?',
  'Build a monthly performance report',
];

export const ChatPage: React.FC = () => {
  const location     = useLocation();
  const scopedContext = location.state?.scopedContext as ScopedContext | undefined;
  const dateRange    = location.state?.dateRange    as DateRange    | undefined;
  const seedMessage  = location.state?.seedMessage  as string       | undefined;

  const {
    messages, isStreaming, streamContent, activeTools, provenanceTools,
    sendMessage, cancelStream, createDiscussion, setActiveDiscussion, error,
  } = useChatStore();

  const [input, setInput] = useState('');
  const bottomRef         = useRef<HTMLDivElement>(null);
  const textareaRef       = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
  }, [input]);

  // Init: create discussion + auto-send if navigated with context
  useEffect(() => {
    (async () => {
      const id = await createDiscussion();
      setActiveDiscussion(id);

      if (seedMessage) {
        await sendMessage(seedMessage);
      } else if (scopedContext?.metric_key) {
        const dr  = dateRange ? `${dateRange.start} to ${dateRange.end}` : 'the current period';
        const msg = `Tell me more about ${scopedContext.label || scopedContext.metric_key} — value: ${scopedContext.value}${
          scopedContext.delta !== undefined
            ? `, ${scopedContext.delta > 0 ? '+' : ''}${scopedContext.delta}% vs prior period`
            : ''
        } for ${dr}.`;
        await sendMessage(msg, scopedContext);
      }
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamContent]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isStreaming) return;
    setInput('');
    await sendMessage(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const isEmpty = messages.length === 0 && !isStreaming && !streamContent;

  return (
    <div className={`cs-chat ${isEmpty ? 'cs-chat--empty' : ''}`}>

      {/* ── Empty state — chibis always visible, no initialization gate ── */}
      {isEmpty && (
        <div className="cs-chat__empty-state">
          <ChibiAvatars />
          <h2 className="cs-chat__empty-title">Ask Cosight anything</h2>
          <p className="cs-chat__empty-sub">Get instant answers about CBS marketing performance.</p>
          <div className="cs-chat__quick-actions">
            {QUICK_ACTIONS.map(q => (
              <button key={q} className="cs-quick-btn" onClick={() => sendMessage(q)}>
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Header (only when messages exist) ── */}
      {!isEmpty && (
        <div className="cs-chat__header">
          <CoSightGlyph state={isStreaming ? 'loading' : 'done'} size={20} />
          <span className="cs-chat__title">Cosight</span>
          <span className="cs-chat__subtitle">CBS Marketing Analytics</span>
        </div>
      )}

      {/* ── Message thread ── */}
      <div className="cs-chat__messages" style={{ display: isEmpty ? 'none' : undefined }}>
        <div className="cs-chat__messages-inner">
          {messages.map(msg => (
            <div key={msg.id} className={`cs-msg cs-msg--${msg.role}`}>
              {msg.role === 'assistant' && (
                <CoSightGlyph state="done" size={24} />
              )}
              <div className="cs-msg__body">
                {msg.report ? (
                  <ReportArtifact artifact={msg.report} compact />
                ) : (
                  <div className="cs-msg__content">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                )}
                {msg.role === 'assistant' && msg.tools_called && msg.tools_called.length > 0 && (
                  <ProvenanceChips tools={msg.tools_called} />
                )}
              </div>
            </div>
          ))}

          {/* Streaming turn */}
          {isStreaming && (
            <div className="cs-msg cs-msg--assistant">
              <CoSightGlyph state="loading" size={24} />
              <div className="cs-msg__body">
                {activeTools.length > 0 && <ToolCallIndicator tools={activeTools} />}
                {streamContent && (
                  <div className="cs-msg__content">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{streamContent}</ReactMarkdown>
                  </div>
                )}
              </div>
            </div>
          )}

          {error && <div className="cs-chat__error">⚠ {error}</div>}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* ── Input — pill style matching Cowork ── */}
      <div className={`cs-chat__input-container ${isEmpty ? 'cs-chat__input-container--centered' : ''}`}>
        <div className="cs-chat__input-wrapper">
          <div className={`cs-chat__input-box ${isStreaming ? 'cs-chat__input-box--active' : ''}`}>
            <textarea
              ref={textareaRef}
              className="cs-chat__textarea"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about performance, trends, or request a report…"
              rows={1}
              disabled={isStreaming}
            />
            {isStreaming ? (
              <button className="cs-chat__send cs-chat__send--stop" onClick={cancelStream} title="Stop">
                <Square size={16} />
              </button>
            ) : (
              <button
                className="cs-chat__send"
                onClick={handleSend}
                disabled={!input.trim()}
                title="Send"
              >
                <ArrowUp size={18} />
              </button>
            )}
          </div>
          <p className="cs-chat__hint">
            Press <kbd>Enter</kbd> to send · <kbd>Shift+Enter</kbd> for new line
          </p>
        </div>
      </div>

    </div>
  );
};
