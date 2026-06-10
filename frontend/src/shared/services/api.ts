import {
  Discussion,
  DiscussionCreate,
  DiscussionUpdate,
  Message,
  MessageRole,
  AttachmentSummary,
  AttachmentDetail,
} from '@/shared/types';
import { supabase } from './supabase';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function getAuthHeaders(): Promise<Record<string, string>> {
  const { data: { session } } = await supabase.auth.getSession();
  if (session?.access_token) {
    return { Authorization: `Bearer ${session.access_token}` };
  }
  return {};
}

class ApiService {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const authHeaders = await getAuthHeaders();
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders,
        ...options?.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'An error occurred' }));
      throw new Error(error.detail || `HTTP error ${response.status}`);
    }

    return response.json();
  }

  async healthCheck() {
    return this.request<{ status: string; providers: Record<string, boolean> }>('/health');
  }

  // Discussions
  async getDiscussions(): Promise<Discussion[]> {
    return this.request<Discussion[]>('/api/discussions');
  }

  async getDiscussion(id: string): Promise<Discussion> {
    return this.request<Discussion>(`/api/discussions/${id}`);
  }

  async createDiscussion(data?: DiscussionCreate): Promise<Discussion> {
    return this.request<Discussion>('/api/discussions', {
      method: 'POST',
      body: JSON.stringify(data || {}),
    });
  }

  async updateDiscussion(id: string, data: DiscussionUpdate): Promise<Discussion> {
    return this.request<Discussion>(`/api/discussions/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteDiscussion(id: string): Promise<void> {
    await this.request(`/api/discussions/${id}`, { method: 'DELETE' });
  }

  async deleteAllDiscussions(): Promise<{ status: string; count: number }> {
    return this.request<{ status: string; count: number }>('/api/discussions', {
      method: 'DELETE',
    });
  }

  async activateDiscussion(id: string): Promise<Discussion> {
    return this.request<Discussion>(`/api/discussions/${id}/activate`, {
      method: 'POST',
    });
  }

  async addMessage(discussionId: string, content: string, role: MessageRole): Promise<Message> {
    return this.request<Message>(`/api/discussions/${discussionId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content, role }),
    });
  }

  getStreamUrl(): string {
    return `${this.baseUrl}/api/chat/stream`;
  }

  // Attachments (conversation-scoped files)
  async uploadAttachment(discussionId: string, file: File): Promise<AttachmentSummary> {
    const authHeaders = await getAuthHeaders();
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(`${this.baseUrl}/api/discussions/${discussionId}/attachments`, {
      method: 'POST',
      headers: authHeaders,
      body: formData,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(error.detail || `HTTP error ${response.status}`);
    }
    return response.json();
  }

  async getAttachments(discussionId: string): Promise<AttachmentSummary[]> {
    return this.request<AttachmentSummary[]>(`/api/discussions/${discussionId}/attachments`);
  }

  async getAttachmentDetail(discussionId: string, attachmentId: string): Promise<AttachmentDetail> {
    return this.request<AttachmentDetail>(`/api/discussions/${discussionId}/attachments/${attachmentId}`);
  }

  async deleteAttachment(discussionId: string, attachmentId: string): Promise<void> {
    await this.request(`/api/discussions/${discussionId}/attachments/${attachmentId}`, { method: 'DELETE' });
  }
}

export const api = new ApiService(API_URL);
