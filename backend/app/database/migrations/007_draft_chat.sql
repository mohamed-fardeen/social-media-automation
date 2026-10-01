-- Migration 007: conversational draft pipeline state
-- (source mode, user topic at entry, image/text mode preference)
-- Idempotent. Run in Supabase SQL Editor.

ALTER TABLE public.post_runs
    ADD COLUMN IF NOT EXISTS image_mode TEXT
        CHECK (image_mode IS NULL OR image_mode IN ('text_only', 'with_image', 'mix')),
    ADD COLUMN IF NOT EXISTS source_mode TEXT
        CHECK (source_mode IS NULL OR source_mode IN ('research', 'user_topic')),
    ADD COLUMN IF NOT EXISTS user_topic TEXT;
