-- ===========================================
-- CoSight Supabase Schema Migration
-- Run in Supabase SQL Editor.
-- Idempotent: safe to re-run (DROP ... IF EXISTS guards all policies).
-- ===========================================

-- 1. cosight_discussions
CREATE TABLE IF NOT EXISTS cosight_discussions (
  id         UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID,   -- nullable until auth is layered in
  title      TEXT    NOT NULL DEFAULT 'New Chat',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cosight_discussions_updated
  ON cosight_discussions(updated_at DESC);

-- 2. cosight_messages
CREATE TABLE IF NOT EXISTS cosight_messages (
  id               UUID  PRIMARY KEY DEFAULT gen_random_uuid(),
  discussion_id    UUID  NOT NULL REFERENCES cosight_discussions(id) ON DELETE CASCADE,
  role             TEXT  NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
  content          TEXT  NOT NULL,
  tokens_used      INTEGER,
  response_time_ms INTEGER,
  created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cosight_messages_discussion
  ON cosight_messages(discussion_id, created_at);

-- 3. cosight_reports — stores the ReportArtifact JSONB payload
CREATE TABLE IF NOT EXISTS cosight_reports (
  id         UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID,
  title      TEXT    NOT NULL DEFAULT 'Untitled Report',
  payload    JSONB   NOT NULL,
  date_range TEXT,   -- "YYYY-MM-DD/YYYY-MM-DD"
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cosight_reports_created
  ON cosight_reports(created_at DESC);

-- 4. cosight_metric_cache — shared connector cache (15-min TTL)
CREATE TABLE IF NOT EXISTS cosight_metric_cache (
  cache_key  TEXT    PRIMARY KEY,
  channel    TEXT    NOT NULL,
  date_range TEXT    NOT NULL,
  payload    JSONB   NOT NULL,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cosight_cache_fetched
  ON cosight_metric_cache(fetched_at);

-- 5. (Optional) cosight_access_log — governance audit trail
CREATE TABLE IF NOT EXISTS cosight_access_log (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID,
  channel      TEXT,
  date_range   TEXT,
  accessed_at  TIMESTAMPTZ DEFAULT now()
);

-- ===========================================
-- RLS policies (no-op when auth not enforced;
-- ready to activate when auth is layered in)
-- ===========================================

ALTER TABLE cosight_discussions ENABLE ROW LEVEL SECURITY;
ALTER TABLE cosight_messages    ENABLE ROW LEVEL SECURITY;
ALTER TABLE cosight_reports     ENABLE ROW LEVEL SECURITY;
ALTER TABLE cosight_metric_cache ENABLE ROW LEVEL SECURITY;

-- Allow service-role key full access (used by backend)
DROP POLICY IF EXISTS "Service role full access cosight_discussions" ON cosight_discussions;
CREATE POLICY "Service role full access cosight_discussions"
  ON cosight_discussions FOR ALL
  USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Service role full access cosight_messages" ON cosight_messages;
CREATE POLICY "Service role full access cosight_messages"
  ON cosight_messages FOR ALL
  USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Service role full access cosight_reports" ON cosight_reports;
CREATE POLICY "Service role full access cosight_reports"
  ON cosight_reports FOR ALL
  USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Service role full access cosight_metric_cache" ON cosight_metric_cache;
CREATE POLICY "Service role full access cosight_metric_cache"
  ON cosight_metric_cache FOR ALL
  USING (true) WITH CHECK (true);
