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

-- 2. Projects table (containers that conversations can be filed under)
CREATE TABLE IF NOT EXISTS projects (
  id                UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID    NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  name              TEXT    NOT NULL DEFAULT 'New Project',
  instructions      TEXT,                         -- the project "theme"/brief
  locked_intent     TEXT,                         -- request type tasks are locked to
  locked_service_type TEXT,                        -- MarComms service_type, when applicable
  icon              TEXT,
  color             TEXT,
  parent_project_id UUID    REFERENCES projects(id) ON DELETE CASCADE,
  created_at        TIMESTAMPTZ DEFAULT now(),
  updated_at        TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_parent  ON projects(parent_project_id);

-- Enforce single-level nesting: a child project cannot itself be a parent.
CREATE OR REPLACE FUNCTION enforce_project_nesting_depth()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.parent_project_id IS NOT NULL THEN
    -- The chosen parent must be a top-level project.
    IF EXISTS (
      SELECT 1 FROM projects
      WHERE id = NEW.parent_project_id AND parent_project_id IS NOT NULL
    ) THEN
      RAISE EXCEPTION 'Projects can only nest one level deep';
    END IF;
    -- This project must not already have children of its own.
    IF EXISTS (SELECT 1 FROM projects WHERE parent_project_id = NEW.id) THEN
      RAISE EXCEPTION 'A project with sub-projects cannot become a sub-project';
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_project_nesting_depth ON projects;
CREATE TRIGGER trg_project_nesting_depth
  BEFORE INSERT OR UPDATE ON projects
  FOR EACH ROW EXECUTE FUNCTION enforce_project_nesting_depth();

ALTER TABLE projects ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own projects"
  ON projects FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own projects"
  ON projects FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own projects"
  ON projects FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own projects"
  ON projects FOR DELETE
  USING (auth.uid() = user_id);

-- 3. Discussions table
CREATE TABLE IF NOT EXISTS discussions (
  id         UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID    NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  project_id UUID    REFERENCES projects(id) ON DELETE SET NULL,  -- NULL = unfiled
  title      TEXT    NOT NULL DEFAULT 'New Chat',
  is_active  BOOLEAN NOT NULL DEFAULT false,
  intent     TEXT,                         -- research | event | media | other
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_discussions_user_id    ON discussions(user_id);
CREATE INDEX IF NOT EXISTS idx_discussions_updated_at ON discussions(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_discussions_project_id ON discussions(project_id);

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

-- 4. Project files table (persistent "Files & sources" shared across a project's tasks)
-- Binary content lives in the 'project-files' Storage bucket at storage_path;
-- extracted_text holds the parsed text used as chat context.
CREATE TABLE IF NOT EXISTS project_files (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id     UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  user_id        UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  filename       TEXT NOT NULL,
  content_type   TEXT,
  size_bytes     INTEGER,
  storage_path   TEXT NOT NULL,
  extracted_text TEXT,
  created_at     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_project_files_project_id ON project_files(project_id);

ALTER TABLE project_files ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read files in own projects"
  ON project_files FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert files in own projects"
  ON project_files FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete files in own projects"
  ON project_files FOR DELETE
  USING (auth.uid() = user_id);

-- Storage bucket for project files (run once; safe to re-run).
INSERT INTO storage.buckets (id, name, public)
VALUES ('project-files', 'project-files', false)
ON CONFLICT (id) DO NOTHING;

CREATE POLICY "Users manage own project files in storage"
  ON storage.objects FOR ALL
  USING (bucket_id = 'project-files' AND owner = auth.uid())
  WITH CHECK (bucket_id = 'project-files' AND owner = auth.uid());

-- 5. Templates table (reusable request starters; can target a hubspace/project)
CREATE TABLE IF NOT EXISTS templates (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  name        TEXT NOT NULL DEFAULT 'New Template',
  description TEXT,
  body        TEXT NOT NULL DEFAULT '',          -- the brief/prompt that seeds the task
  hubspace_id UUID REFERENCES projects(id) ON DELETE SET NULL,  -- optional target hubspace
  icon        TEXT,
  color       TEXT,
  created_at  TIMESTAMPTZ DEFAULT now(),
  updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_templates_user_id ON templates(user_id);

ALTER TABLE templates ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own templates"
  ON templates FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own templates"
  ON templates FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own templates"
  ON templates FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own templates"
  ON templates FOR DELETE
  USING (auth.uid() = user_id);

-- Learned field defaults: per user (optionally per hubspace) remembered answers
-- for a given request type. Pre-fills the intake checklist so recurring tickets
-- stop re-asking predictable fields. confidence drives ask -> suggest -> silent.
CREATE TABLE IF NOT EXISTS field_defaults (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  hubspace_id    UUID REFERENCES projects(id) ON DELETE CASCADE,  -- NULL = user-global
  service_type   TEXT NOT NULL,                  -- scopes a default to a request type
  field          TEXT NOT NULL,                  -- e.g. 'contact_name', 'details'
  value          TEXT NOT NULL,
  confidence     INT  NOT NULL DEFAULT 1,        -- repeat count; drives ask -> suggest -> silent
  always_confirm BOOLEAN NOT NULL DEFAULT false, -- high-stakes: pre-fill but never go silent
  updated_at     TIMESTAMPTZ DEFAULT now(),
  UNIQUE (user_id, hubspace_id, service_type, field)
);

CREATE INDEX IF NOT EXISTS idx_field_defaults_lookup
  ON field_defaults(user_id, service_type);

ALTER TABLE field_defaults ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own field_defaults"
  ON field_defaults FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own field_defaults"
  ON field_defaults FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own field_defaults"
  ON field_defaults FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own field_defaults"
  ON field_defaults FOR DELETE
  USING (auth.uid() = user_id);

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

-- ===========================================
-- Migration: add Projects feature
-- Run on existing Cowork databases.
-- Re-run the full schema above first (it creates the
-- projects / project_files tables and policies idempotently),
-- then this only needs to backfill the discussions column.
-- ===========================================
ALTER TABLE discussions
  ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_discussions_project_id ON discussions(project_id);
