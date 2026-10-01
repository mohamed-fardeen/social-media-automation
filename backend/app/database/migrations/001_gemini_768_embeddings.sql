-- Migration 001: Update vector dimension to 768 for Gemini Embeddings (gemini-embedding-001)

-- 1. Drop existing HNSW index
DROP INDEX IF EXISTS public.knowledge_chunks_embedding_hnsw_idx;

-- 2. Drop existing match function signatures
DROP FUNCTION IF EXISTS public.match_knowledge_chunks(vector, float, int);
DROP FUNCTION IF EXISTS public.match_knowledge_chunks(vector(1536), float, int);
DROP FUNCTION IF EXISTS public.match_knowledge_chunks(vector(384), float, int);

-- 3. Ensure source_label column exists
ALTER TABLE public.knowledge_chunks 
ADD COLUMN IF NOT EXISTS source_label TEXT;

-- 4. Safely clear old embeddings so column type alter can succeed without dropping data
UPDATE public.knowledge_chunks 
SET embedding = NULL;

-- 5. Alter vector column to vector(768)
ALTER TABLE public.knowledge_chunks 
ALTER COLUMN embedding TYPE vector(768);

-- 6. Re-create HNSW vector index for 768 dimensions
CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_hnsw_idx 
ON public.knowledge_chunks 
USING hnsw (embedding vector_cosine_ops);

-- 7. Re-create match_knowledge_chunks function with vector(768)
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
