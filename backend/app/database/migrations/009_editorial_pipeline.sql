-- Migration 009: Support for Editorial Pipeline, Content Intelligence, and QA Gates
-- Safe & idempotent. Run in Supabase SQL Editor.

-- ─── post_runs: store editorial brief, opportunities, and QA metrics ─────────
ALTER TABLE public.post_runs
    ADD COLUMN IF NOT EXISTS editorial_brief JSONB,
    ADD COLUMN IF NOT EXISTS content_opportunities JSONB,
    ADD COLUMN IF NOT EXISTS qa_results JSONB,
    ADD COLUMN IF NOT EXISTS repetition_warning TEXT;

-- ─── post_drafts: store editorial brief, visual spec, QA and claim evidence ──
ALTER TABLE public.post_drafts
    ADD COLUMN IF NOT EXISTS editorial_brief JSONB,
    ADD COLUMN IF NOT EXISTS visual_spec JSONB,
    ADD COLUMN IF NOT EXISTS qa_results JSONB,
    ADD COLUMN IF NOT EXISTS claim_evidence JSONB,
    ADD COLUMN IF NOT EXISTS visual_type TEXT;
