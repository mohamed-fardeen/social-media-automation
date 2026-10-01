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
