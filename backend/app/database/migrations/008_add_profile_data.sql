-- Step 1 migration: Add profile_data JSONB column to public.brand_profiles
ALTER TABLE public.brand_profiles
ADD COLUMN IF NOT EXISTS profile_data JSONB NOT NULL DEFAULT '{}'::jsonb;
