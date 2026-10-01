-- Migration 006: per-idea post format + image hint persistence
-- Idempotent. Run in Supabase SQL Editor.

ALTER TABLE public.post_drafts
    ADD COLUMN IF NOT EXISTS format TEXT,
    ADD COLUMN IF NOT EXISTS format_label TEXT,
    ADD COLUMN IF NOT EXISTS image_hint TEXT;
