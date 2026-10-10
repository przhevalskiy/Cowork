/**
 * AgentInputBar — same pill-shaped input as Cowork's ChatInput,
 * adapted for CoSight's agentic chat endpoint.
 * Used on the Overview page to let users ask questions without
 * leaving the dashboard.
 */
import React, { useState, useRef, useEffect } from 'react';
import { ArrowUp, Square } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useChatStore } from '../../stores/chatStore';
import { OVERVIEW_PROMPTS, type DashboardPrompt } from './dashboardPrompts';
import './AgentInputBar.css';

interface Props {
  /** If true, navigates to /chat on submit instead of streaming inline */
  navigateOnSend?: boolean;
  quickPrompts?: DashboardPrompt[];
  placeholder?: string;
}

export const AgentInputBar: React.FC<Props> = ({
  navigateOnSend = true,
  quickPrompts = OVERVIEW_PROMPTS,
  placeholder = 'Ask CoSight anything about your marketing data…',
}) => {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const navigate = useNavigate();
  const { sendMessage, isStreaming, cancelStream, createDiscussion, setActiveDiscussion } = useChatStore();

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
  }, [input]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isStreaming) return;
    setInput('');

    if (navigateOnSend) {
      // Create a new discussion and navigate to chat with pre-seeded message
      const id = await createDiscussion();
      setActiveDiscussion(id);
      navigate('/chat', { state: { seedMessage: text } });
    } else {
      await sendMessage(text);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleQuickPrompt = (prompt: string) => {
    if (navigateOnSend) {
      navigate('/chat', { state: { seedMessage: prompt } });
    } else {
      sendMessage(prompt);
    }
  };

  return (
    <div className="agent-input-bar">
      <div className={`agent-input-box ${isStreaming ? 'agent-input-box--streaming' : ''}`}>
        <textarea
          ref={textareaRef}
          className="agent-textarea"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          rows={1}
          disabled={isStreaming}
        />
        {isStreaming ? (
          <button className="agent-send-btn agent-send-btn--stop" onClick={cancelStream} title="Stop">
            <Square size={16} />
          </button>
        ) : (
          <button
            className="agent-send-btn"
            onClick={handleSend}
            disabled={!input.trim()}
            title="Send"
          >
            <ArrowUp size={18} />
          </button>
        )}
      </div>

      <div className="agent-quick-prompts">
        {quickPrompts.map(q => (
          <button
            key={q.label}
            className="agent-quick-btn"
            onClick={() => handleQuickPrompt(q.prompt)}
            disabled={isStreaming}
          >
            {q.label}
          </button>
        ))}
      </div>
    </div>
  );
};
