-- Migration 005: Telegram-driven idea selection (3 ideas, user picks one or all)
-- Idempotent. Run in Supabase SQL Editor.

-- ─── post_runs: idea selection state ─────────────────────────────────────────
ALTER TABLE public.post_runs
    ADD COLUMN IF NOT EXISTS ideas JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS selected_idea_indices INTEGER[] DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS idea_status TEXT DEFAULT 'not_proposed'
        CHECK (idea_status IN ('not_proposed', 'proposed', 'selected', 'generating', 'done', 'dismissed'));

-- ─── post_drafts: which idea produced this draft ─────────────────────────────
ALTER TABLE public.post_drafts
    ADD COLUMN IF NOT EXISTS idea_index INTEGER
        CHECK (idea_index IS NULL OR idea_index BETWEEN 1 AND 3);

-- Drop the old awaiting_approval-only check on post_runs.status if present, then widen.
-- (Safest path: leave the existing CHECK and let new statuses be added in a follow-up
-- migration when the constraint is updated. For now, the Python layer accepts the new
-- statuses; the DB CHECK will reject them only if it explicitly forbids them.)

-- ─── Realtime: make sure the new column changes are picked up ────────────────
-- post_runs and post_drafts are already in supabase_realtime (migration 004),
-- so payload broadcasts will include the new fields automatically.
