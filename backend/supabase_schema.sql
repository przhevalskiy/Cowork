-- ===========================================
-- Cowork Supabase Schema
-- Run this in Supabase SQL Editor (fresh install)
-- For existing Qodex DBs, run the migration
-- section at the bottom first.
-- ===========================================

-- 1. Profiles table (auto-populated from auth.users)
CREATE TABLE IF NOT EXISTS profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email TEXT,
  display_name TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own profile"
  ON profiles FOR SELECT
  USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
  ON profiles FOR UPDATE
  USING (auth.uid() = id);

-- Auto-create profile on signup
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO profiles (id, email, display_name)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'display_name', split_part(NEW.email, '@', 1))
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- 2. Discussions table
CREATE TABLE IF NOT EXISTS discussions (
  id         UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID    NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  title      TEXT    NOT NULL DEFAULT 'New Chat',
  is_active  BOOLEAN NOT NULL DEFAULT false,
  intent     TEXT,                         -- research | event | media | other
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_discussions_user_id    ON discussions(user_id);
CREATE INDEX IF NOT EXISTS idx_discussions_updated_at ON discussions(updated_at DESC);

ALTER TABLE discussions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own discussions"
  ON discussions FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own discussions"
  ON discussions FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own discussions"
  ON discussions FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own discussions"
  ON discussions FOR DELETE
  USING (auth.uid() = user_id);

-- 3. Messages table
CREATE TABLE IF NOT EXISTS messages (
  id              UUID  PRIMARY KEY DEFAULT gen_random_uuid(),
  discussion_id   UUID  NOT NULL REFERENCES discussions(id) ON DELETE CASCADE,
  role            TEXT  NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
  content         TEXT  NOT NULL,
  tokens_used     INTEGER,
  response_time_ms INTEGER,
  intent          TEXT,
  user_display_name TEXT,
  user_email      TEXT,
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_messages_discussion_id      ON messages(discussion_id);
CREATE INDEX IF NOT EXISTS idx_messages_discussion_created ON messages(discussion_id, created_at);

ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read messages in own discussions"
  ON messages FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM discussions
      WHERE discussions.id = messages.discussion_id
        AND discussions.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can insert messages in own discussions"
  ON messages FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM discussions
      WHERE discussions.id = messages.discussion_id
        AND discussions.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can update messages in own discussions"
  ON messages FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM discussions
      WHERE discussions.id = messages.discussion_id
        AND discussions.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can delete messages in own discussions"
  ON messages FOR DELETE
  USING (
    EXISTS (
      SELECT 1 FROM discussions
      WHERE discussions.id = messages.discussion_id
        AND discussions.user_id = auth.uid()
    )
  );

-- ===========================================
-- Migration: Qodex → Cowork
-- Run this block on existing Qodex databases
-- BEFORE applying the schema above.
-- ===========================================

-- Drop legacy tables
DROP TABLE IF EXISTS document_formatted_chunks;

-- discussions: remove share column, add intent
ALTER TABLE discussions DROP COLUMN IF EXISTS is_public;
ALTER TABLE discussions ADD COLUMN IF NOT EXISTS intent TEXT;
DROP INDEX IF EXISTS idx_discussions_is_public;

-- messages: drop columns removed in Cowork
ALTER TABLE messages DROP COLUMN IF EXISTS provider;
ALTER TABLE messages DROP COLUMN IF EXISTS sources;
ALTER TABLE messages DROP COLUMN IF EXISTS citations;
ALTER TABLE messages DROP COLUMN IF EXISTS suggested_questions;
ALTER TABLE messages DROP COLUMN IF EXISTS research_mode;

-- Drop old share policies (safe if they don't exist)
DROP POLICY IF EXISTS "Authenticated users can read public discussions" ON discussions;
DROP POLICY IF EXISTS "Authenticated users can read messages in public discussions" ON messages;
