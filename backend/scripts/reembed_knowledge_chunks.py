"""
Re-embed script for Gemini Embeddings (768 dimensions).
Re-embeds existing knowledge chunks or document text using gemini-embedding-001.
"""
import sys
import os

# Ensure backend root is on sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.database.supabase_client import get_supabase_client
from app.services.rag.embedder import EmbeddingProvider
from app.config.logging import logger

def reembed_all_chunks():
    supa = get_supabase_client()
    if not supa:
        logger.error("Supabase client not available for re-embedding.")
        return 0

    embedder = EmbeddingProvider()
    if not embedder.available:
        logger.error("EmbeddingProvider (GEMINI_API_KEY) not available.")
        return 0

    logger.info("Fetching existing knowledge chunks from Supabase...")
    try:
        res = supa.table("knowledge_chunks").select("id, content").execute()
        chunks = res.data or []
    except Exception as e:
        logger.error(f"Failed to fetch knowledge chunks: {e}")
        return 0

    if not chunks:
        logger.info("No knowledge chunks found in database to re-embed.")
        return 0

    logger.info(f"Re-embedding {len(chunks)} chunks using model '{embedder.model}' (dim {embedder.dimension})...")
    
    contents = [c.get("content", "") for c in chunks]
    embeddings = embedder.embed_batch(contents)

    updated_count = 0
    for chunk_obj, emb in zip(chunks, embeddings):
        if not emb:
            logger.warning(f"Skipping chunk {chunk_obj['id']}: Failed to generate embedding.")
            continue

        try:
            supa.table("knowledge_chunks").update({"embedding": emb}).eq("id", chunk_obj["id"]).execute()
            updated_count += 1
        except Exception as e:
            logger.error(f"Failed to update embedding for chunk {chunk_obj['id']}: {e}")

    logger.info(f"Successfully re-embedded {updated_count}/{len(chunks)} knowledge chunks.")
    return updated_count

if __name__ == "__main__":
    reembed_all_chunks()
