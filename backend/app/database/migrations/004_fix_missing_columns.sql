-- Migration 004: Fix missing columns & tables in the live Supabase database
-- Run this in the Supabase SQL Editor at:
-- https://app.supabase.com → SQL Editor → New Query → paste & run

-- ─── post_runs: add missing columns ──────────────────────────────────────────
ALTER TABLE public.post_runs
    ADD COLUMN IF NOT EXISTS current_agent TEXT,
    ADD COLUMN IF NOT EXISTS notes TEXT,
    ADD COLUMN IF NOT EXISTS topic_hint TEXT;

-- ─── post_drafts: add missing columns ────────────────────────────────────────
ALTER TABLE public.post_drafts
    ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS scheduled_for TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS image_prompt TEXT,
    ADD COLUMN IF NOT EXISTS strategy TEXT,
    ADD COLUMN IF NOT EXISTS reasoning TEXT,
    ADD COLUMN IF NOT EXISTS metrics JSONB DEFAULT '{}'::jsonb;

-- ─── agent_logs: add missing columns ─────────────────────────────────────────
-- The table may have been created without the 'agent' column
ALTER TABLE public.agent_logs
    ADD COLUMN IF NOT EXISTS agent TEXT,
    ADD COLUMN IF NOT EXISTS model TEXT,
    ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS input_summary TEXT,
    ADD COLUMN IF NOT EXISTS output_summary TEXT,
    ADD COLUMN IF NOT EXISTS latency_ms INTEGER,
    ADD COLUMN IF NOT EXISTS tokens_in INTEGER,
    ADD COLUMN IF NOT EXISTS tokens_out INTEGER,
    ADD COLUMN IF NOT EXISTS error TEXT;

-- ─── workflow_checkpoints: create table if missing ────────────────────────────
CREATE TABLE IF NOT EXISTS public.workflow_checkpoints (
    run_id TEXT PRIMARY KEY,
    checkpoint_data JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── research_insights: ensure table exists ───────────────────────────────────
CREATE TABLE IF NOT EXISTS public.research_insights (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    source TEXT NOT NULL,
    source_kind TEXT NOT NULL DEFAULT 'trend',
    url TEXT,
    tags TEXT[] DEFAULT '{}',
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    related_count INTEGER DEFAULT 0
);

-- ─── Enable Realtime (safe to run again) ─────────────────────────────────────
-- These may already be set; the IF NOT EXISTS-equivalent is to use DO blocks
DO $$
BEGIN
    BEGIN
        ALTER PUBLICATION supabase_realtime ADD TABLE public.post_runs;
    EXCEPTION WHEN duplicate_object THEN NULL;
    END;
    BEGIN
        ALTER PUBLICATION supabase_realtime ADD TABLE public.post_drafts;
    EXCEPTION WHEN duplicate_object THEN NULL;
    END;
    BEGIN
        ALTER PUBLICATION supabase_realtime ADD TABLE public.agent_logs;
    EXCEPTION WHEN duplicate_object THEN NULL;
    END;
END
$$;
