/**
 * CoSight API client — all calls go through this service.
 * No raw vendor JSON ever reaches a component.
 */
import type {
  ChannelMetrics,
  OverviewPayload,
  ReportArtifact,
  CoSightMessage,
  DateRange,
} from '../types';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

function dateParams(range: DateRange): string {
  return `?start=${range.start}&end=${range.end}`;
}

// ── Metrics ───────────────────────────────────────────────────────────────────

export async function getWebMetrics(range: DateRange): Promise<ChannelMetrics> {
  return request(`/api/cosight/web${dateParams(range)}`);
}

export async function getSeoMetrics(range: DateRange): Promise<ChannelMetrics> {
  return request(`/api/cosight/seo${dateParams(range)}`);
}

export async function getEmailMetrics(range: DateRange): Promise<ChannelMetrics> {
  return request(`/api/cosight/email${dateParams(range)}`);
}

export async function getSocialMetrics(range: DateRange): Promise<ChannelMetrics> {
  return request(`/api/cosight/social${dateParams(range)}`);
}

export async function getOverview(range: DateRange): Promise<OverviewPayload> {
  return request(`/api/cosight/overview${dateParams(range)}`);
}

export function getChannelCsvUrl(channel: string, range: DateRange): string {
  return `${API_URL}/api/cosight/${channel}/export.csv?start=${range.start}&end=${range.end}`;
}

// ── Reports ───────────────────────────────────────────────────────────────────

export async function saveReport(artifact: ReportArtifact): Promise<{ id: string }> {
  return request('/api/cosight/reports', {
    method: 'POST',
    body: JSON.stringify(artifact),
  });
}

export async function listReports(): Promise<Array<{ id: string; title: string; date_range: string; created_at: string }>> {
  return request('/api/cosight/reports');
}

export async function getReport(id: string): Promise<ReportArtifact> {
  return request(`/api/cosight/reports/${id}`);
}

export function getReportExportUrl(id: string, format: 'slides' | 'csv'): string {
  return `${API_URL}/api/cosight/reports/${id}/export?format=${format}`;
}

// ── Chat discussions ──────────────────────────────────────────────────────────

export async function listDiscussions(): Promise<Array<{ id: string; title: string; updated_at: string }>> {
  return request('/api/cosight/chat/discussions');
}

export async function createDiscussion(): Promise<{ id: string; title: string }> {
  return request('/api/cosight/chat/discussions', { method: 'POST' });
}

export async function deleteDiscussion(id: string): Promise<void> {
  await request(`/api/cosight/chat/discussions/${id}`, { method: 'DELETE' });
}

// ── Streaming chat ────────────────────────────────────────────────────────────

export interface StreamChatOptions {
  discussion_id: string;
  message: string;
  scoped_context?: {
    channel?: string;
    metric_key?: string;
    date_range?: string;
    value?: number;
    delta?: number;
  };
  onChunk: (text: string) => void;
  onToolCall: (tool: string) => void;
  onProvenance: (tools: string[]) => void;
  onReport: (reportId: string, artifact: ReportArtifact) => void;
  onTitleUpdate: (discussionId: string, title: string) => void;
  onDone: () => void;
  onError: (msg: string) => void;
  signal?: AbortSignal;
}

export async function streamChat(opts: StreamChatOptions): Promise<void> {
  const res = await fetch(`${API_URL}/api/cosight/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      discussion_id: opts.discussion_id,
      message: opts.message,
      scoped_context: opts.scoped_context,
    }),
    signal: opts.signal,
  });

  if (!res.ok) {
    throw new Error(`Chat stream failed: HTTP ${res.status}`);
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      try {
        const event = JSON.parse(line.slice(6));
        switch (event.type) {
          case 'chunk':
            opts.onChunk(event.content);
            break;
          case 'tool_call':
            opts.onToolCall(event.tool);
            break;
          case 'provenance':
            opts.onProvenance(event.tools);
            break;
          case 'report':
            opts.onReport(event.report_id, event.artifact);
            break;
          case 'discussion_title':
            opts.onTitleUpdate(event.discussion_id, event.title);
            break;
          case 'error':
            opts.onError(event.error);
            break;
          case 'done':
            opts.onDone();
            return;
        }
      } catch {
        // skip malformed event
      }
    }
  }
}
