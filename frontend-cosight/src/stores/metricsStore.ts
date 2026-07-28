/**
 * Zustand store for CoSight metrics state.
 * One date-range source drives every query — invariant enforced here.
 */
import { create } from 'zustand';
import type { ChannelMetrics, DateRange, OverviewPayload } from '../types';
import * as api from '../services/api';

function defaultRange(): DateRange {
  const end = new Date();
  end.setDate(end.getDate() - 1);
  const start = new Date(end);
  start.setDate(start.getDate() - 29);
  return {
    start: start.toISOString().split('T')[0],
    end: end.toISOString().split('T')[0],
  };
}

interface MetricsState {
  dateRange: DateRange;
  overview: OverviewPayload | null;
  web: ChannelMetrics | null;
  seo: ChannelMetrics | null;
  email: ChannelMetrics | null;
  social: ChannelMetrics | null;
  loading: Record<string, boolean>;
  errors: Record<string, string | null>;
}

interface MetricsActions {
  setDateRange: (range: DateRange) => void;
  fetchOverview: () => Promise<void>;
  fetchWeb: () => Promise<void>;
  fetchSeo: () => Promise<void>;
  fetchEmail: () => Promise<void>;
  fetchSocial: () => Promise<void>;
}

export const useMetricsStore = create<MetricsState & MetricsActions>((set, get) => ({
  dateRange: defaultRange(),
  overview: null,
  web: null,
  seo: null,
  email: null,
  social: null,
  loading: {},
  errors: {},

  setDateRange: (range) => set({ dateRange: range }),

  fetchOverview: async () => {
    const range = get().dateRange;
    set(s => ({ loading: { ...s.loading, overview: true }, errors: { ...s.errors, overview: null } }));
    try {
      const data = await api.getOverview(range);
      set({ overview: data });
    } catch (e) {
      set(s => ({ errors: { ...s.errors, overview: (e as Error).message } }));
    } finally {
      set(s => ({ loading: { ...s.loading, overview: false } }));
    }
  },

  fetchWeb: async () => {
    const range = get().dateRange;
    set(s => ({ loading: { ...s.loading, web: true }, errors: { ...s.errors, web: null } }));
    try {
      const data = await api.getWebMetrics(range);
      set({ web: data });
    } catch (e) {
      set(s => ({ errors: { ...s.errors, web: (e as Error).message } }));
    } finally {
      set(s => ({ loading: { ...s.loading, web: false } }));
    }
  },

  fetchSeo: async () => {
    const range = get().dateRange;
    set(s => ({ loading: { ...s.loading, seo: true }, errors: { ...s.errors, seo: null } }));
    try {
      const data = await api.getSeoMetrics(range);
      set({ seo: data });
    } catch (e) {
      set(s => ({ errors: { ...s.errors, seo: (e as Error).message } }));
    } finally {
      set(s => ({ loading: { ...s.loading, seo: false } }));
    }
  },

  fetchEmail: async () => {
    const range = get().dateRange;
    set(s => ({ loading: { ...s.loading, email: true }, errors: { ...s.errors, email: null } }));
    try {
      const data = await api.getEmailMetrics(range);
      set({ email: data });
    } catch (e) {
      set(s => ({ errors: { ...s.errors, email: (e as Error).message } }));
    } finally {
      set(s => ({ loading: { ...s.loading, email: false } }));
    }
  },

  fetchSocial: async () => {
    const range = get().dateRange;
    set(s => ({ loading: { ...s.loading, social: true }, errors: { ...s.errors, social: null } }));
    try {
      const data = await api.getSocialMetrics(range);
      set({ social: data });
    } catch (e) {
      set(s => ({ errors: { ...s.errors, social: (e as Error).message } }));
    } finally {
      set(s => ({ loading: { ...s.loading, social: false } }));
    }
  },
}));
