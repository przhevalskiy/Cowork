import { create } from 'zustand';
import type { CoSightMessage, ReportArtifact, ScopedContext } from '../types';
import * as api from '../services/api';

interface ChatState {
  discussions: Array<{ id: string; title: string; updated_at: string }>;
  discussionsLoading: boolean;
  activeDiscussionId: string | null;
  messages: CoSightMessage[];
  isStreaming: boolean;
  streamContent: string;
  activeTools: string[];
  provenanceTools: string[];
  error: string | null;
}

interface ChatActions {
  loadDiscussions: () => Promise<void>;
  createDiscussion: () => Promise<string>;
  setActiveDiscussion: (id: string | null) => void;
  sendMessage: (message: string, scopedContext?: ScopedContext) => Promise<void>;
  cancelStream: () => void;
  clearMessages: () => void;
}

let abortController: AbortController | null = null;

export const useChatStore = create<ChatState & ChatActions>((set, get) => ({
  discussions: [],
  discussionsLoading: false,
  activeDiscussionId: null,
  messages: [],
  isStreaming: false,
  streamContent: '',
  activeTools: [],
  provenanceTools: [],
  error: null,

  loadDiscussions: async () => {
    set({ discussionsLoading: true });
    try {
      const data = await api.listDiscussions();
      set({ discussions: data, discussionsLoading: false });
    } catch (e) {
      set({ error: (e as Error).message, discussionsLoading: false });
    }
  },

  createDiscussion: async () => {
    const d = await api.createDiscussion();
    set(s => ({ discussions: [{ id: d.id, title: d.title, updated_at: new Date().toISOString() }, ...s.discussions] }));
    return d.id;
  },

  setActiveDiscussion: (id) => {
    set({ activeDiscussionId: id, messages: [], streamContent: '', provenanceTools: [] });
  },

  sendMessage: async (message, scopedContext) => {
    const state = get();
    let discussionId = state.activeDiscussionId;
    if (!discussionId) {
      discussionId = await get().createDiscussion();
      set({ activeDiscussionId: discussionId });
    }

    const userMsg: CoSightMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    };
    set(s => ({
      messages: [...s.messages, userMsg],
      isStreaming: true,
      streamContent: '',
      activeTools: [],
      provenanceTools: [],
      error: null,
    }));

    abortController = new AbortController();
    const assistantId = crypto.randomUUID();

    await api.streamChat({
      discussion_id: discussionId,
      message,
      scoped_context: scopedContext,
      signal: abortController.signal,
      onChunk: (text) => set(s => ({ streamContent: s.streamContent + text })),
      onToolCall: (tool) => set(s => ({ activeTools: [...new Set([...s.activeTools, tool])] })),
      onProvenance: (tools) => set({ provenanceTools: tools, activeTools: [] }),
      onReport: (reportId, artifact) => {
        const reportMsg: CoSightMessage = {
          id: `report-${reportId}`,
          role: 'assistant',
          content: '',
          timestamp: new Date().toISOString(),
          report: artifact,
        };
        set(s => ({ messages: [...s.messages, reportMsg] }));
      },
      onTitleUpdate: (discId, title) => {
        set(s => ({
          discussions: s.discussions.map(d => d.id === discId ? { ...d, title } : d),
        }));
      },
      onDone: () => {
        const content = get().streamContent;
        if (content.trim()) {
          const assistantMsg: CoSightMessage = {
            id: assistantId,
            role: 'assistant',
            content,
            timestamp: new Date().toISOString(),
            tools_called: get().provenanceTools,
          };
          set(s => ({ messages: [...s.messages, assistantMsg] }));
        }
        set({ isStreaming: false, streamContent: '', activeTools: [] });
      },
      onError: (msg) => {
        set({ error: msg, isStreaming: false, streamContent: '', activeTools: [] });
      },
    });
  },

  cancelStream: () => {
    abortController?.abort();
    const content = get().streamContent;
    if (content.trim()) {
      set(s => ({
        messages: [...s.messages, {
          id: crypto.randomUUID(),
          role: 'assistant' as const,
          content,
          timestamp: new Date().toISOString(),
        }],
      }));
    }
    set({ isStreaming: false, streamContent: '', activeTools: [] });
  },

  clearMessages: () => set({ messages: [], streamContent: '', error: null }),
}));
