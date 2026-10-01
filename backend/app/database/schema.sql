-- Kelvin6k Social Engine V2 Supabase Schema Migration Script
-- Enable vector extension for RAG knowledge embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table
-- `documents` mirrors the deployed Supabase table: only id, file_name, mime_type,
-- status, storage_path, created_at and error are stored on this row.
-- Chunk count is derived from `knowledge_chunks` rows where document_id = documents.id
-- (no denormalized `chunks` / `pages` columns — see store.ingest_count).
CREATE TABLE IF NOT EXISTS public.documents (
    id TEXT PRIMARY KEY,
    file_name TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'uploading',
    storage_path TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    error TEXT
);

-- Company / brand setup used as base context for RAG and research.
CREATE TABLE IF NOT EXISTS public.brand_profiles (
    id TEXT PRIMARY KEY DEFAULT 'default',
    company_name TEXT NOT NULL,
    website TEXT,
    industry TEXT NOT NULL,
    target_audience TEXT NOT NULL,
    products_services TEXT,
    brand_voice TEXT,
    competitors TEXT[] DEFAULT '{}',
    instagram_handle TEXT,
    linkedin_handle TEXT,
    goals TEXT,
    content_themes TEXT[] DEFAULT '{}',
    approval_channel TEXT DEFAULT 'none',
    telegram_bot_token TEXT,
    telegram_chat_id TEXT,
    telegram_webhook_secret TEXT,
    profile_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Knowledge Chunks table with vector support (Gemini Embeddings 768 dimensions)
CREATE TABLE IF NOT EXISTS public.knowledge_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(768),
    source_label TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create index for vector similarity search using HNSW
CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_hnsw_idx 
ON public.knowledge_chunks 
USING hnsw (embedding vector_cosine_ops);


-- Post Runs table
CREATE TABLE IF NOT EXISTS public.post_runs (
    id TEXT PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'queued',
    trigger TEXT NOT NULL DEFAULT 'manual',
    draft_ids TEXT[] DEFAULT '{}',
    current_agent TEXT,
    notes TEXT,
    topic_hint TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Post Drafts table
CREATE TABLE IF NOT EXISTS public.post_drafts (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES public.post_runs(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    caption TEXT NOT NULL,
    hashtags TEXT[] DEFAULT '{}',
    image_url TEXT,
    image_prompt TEXT,
    strategy TEXT,
    reasoning TEXT,
    status TEXT NOT NULL DEFAULT 'pending_approval',
    scheduled_for TIMESTAMPTZ,
    published_at TIMESTAMPTZ,
    metrics JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Agent Logs table for observability & Supabase Realtime
CREATE TABLE IF NOT EXISTS public.agent_logs (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES public.post_runs(id) ON DELETE CASCADE,
    agent TEXT NOT NULL,
    model TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',
    input_summary TEXT,
    output_summary TEXT,
    latency_ms INTEGER,
    tokens_in INTEGER,
    tokens_out INTEGER,
    metadata JSONB DEFAULT '{}'::jsonb,
    error TEXT
);

-- Publish Results table
CREATE TABLE IF NOT EXISTS public.publish_results (
    id TEXT PRIMARY KEY,
    draft_id TEXT NOT NULL REFERENCES public.post_drafts(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    external_url TEXT,
    status TEXT NOT NULL,
    error TEXT
);

-- Research Insights table
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

-- LangGraph State Checkpoints table for persistent workflow resumption
CREATE TABLE IF NOT EXISTS public.workflow_checkpoints (
    run_id TEXT PRIMARY KEY,
    checkpoint_data JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- RPC Function for Similarity Match Chunks
CREATE OR REPLACE FUNCTION match_knowledge_chunks (
  query_embedding vector(768),
  match_threshold float,
  match_count int
)
RETURNS TABLE (
  id text,
  document_id text,
  content text,
  metadata jsonb,
  source_label text,
  similarity float
)

LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    kc.id,
    kc.document_id,
    kc.content,
    kc.metadata,
    kc.source_label,
    1 - (kc.embedding <=> query_embedding) AS similarity
  FROM public.knowledge_chunks kc
  WHERE 1 - (kc.embedding <=> query_embedding) > match_threshold
  ORDER BY kc.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- Enable Supabase Realtime publication on post_runs, post_drafts, agent_logs
ALTER PUBLICATION supabase_realtime ADD TABLE public.post_runs;
ALTER PUBLICATION supabase_realtime ADD TABLE public.post_drafts;
ALTER PUBLICATION supabase_realtime ADD TABLE public.agent_logs;
