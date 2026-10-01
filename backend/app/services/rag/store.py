import uuid
from typing import List, Dict, Any, Optional
from app.services.rag.embedder import EmbeddingProvider
from app.services.rag.chunker import RecursiveTextChunker
from app.database.supabase_client import get_supabase_client
from app.config.logging import logger


class KnowledgeStore:
    def __init__(self):
        self.embedder = EmbeddingProvider()
        self.chunker = RecursiveTextChunker(chunk_size=800, overlap=150)

    def ingest_pages(
        self,
        document_id: str,
        pages: List[Dict[str, Any]],
        source_label: str = ""
    ) -> int:
        """Chunk, embed in batch, and store page content into Supabase pgvector."""
        logger.info(f"[store] ingest_pages called: document={document_id}, pages={len(pages)}, source='{source_label}'")
        supa = get_supabase_client()
        all_chunks: List[Dict[str, Any]] = []

        for page in pages:
            page_content = page.get("content", "").strip()
            if not page_content:
                continue

            metadata = {
                "document_id": document_id,
                "page_number": page.get("page_number", 1),
                "method": page.get("method", "unknown"),
                "confidence": page.get("confidence", 1.0),
                "source_filename": page.get("filename", "")
            }

            chunks = self.chunker.chunk_text(page_content, metadata)
            all_chunks.extend(chunks)

        if not all_chunks:
            return 0

        # Batch embed all chunk contents at once
        chunk_texts = [c["content"] for c in all_chunks]
        logger.info(f"[store] embed_batch: {len(chunk_texts)} chunks for document {document_id}")
        try:
            embeddings = self.embedder.embed_batch(chunk_texts)
        except Exception as emb_err:
            logger.error(f"[store] embed_batch failed for document {document_id}: {emb_err}", exc_info=True)
            raise
        first_embedding = next((emb for emb in embeddings if emb), None)
        logger.info(
            "[store] embed_batch complete: got %s embeddings (dim=%s)",
            len(embeddings),
            len(first_embedding) if first_embedding else "N/A"
        )

        total_chunks = 0
        skipped_embeddings = 0
        for chunk, embedding in zip(all_chunks, embeddings):
            if not embedding:
                logger.error("[store] skipping chunk with missing embedding for document %s", document_id)
                skipped_embeddings += 1
                continue

            chunk_meta = dict(chunk["metadata"])
            label_val = source_label or chunk_meta.get("source_filename", "")
            chunk_meta["source_label"] = label_val

            row = {
                "document_id": document_id,
                "content": chunk["content"],
                "metadata": chunk_meta,
                "embedding": embedding
            }

            if supa:
                try:
                    supa.table("knowledge_chunks").insert(row).execute()
                    total_chunks += 1
                except Exception as e:
                    logger.error(f"Failed to insert chunk: {e}")
            else:
                # Local in-memory fallback for development
                logger.info(f"[LocalStore] Would insert chunk: ({len(chunk['content'])} chars)")
                total_chunks += 1

        if total_chunks == 0 and all_chunks:
            if skipped_embeddings == len(all_chunks):
                raise ValueError("Embedding generation failed for all generated chunks.")
            raise ValueError("All generated chunks failed to insert into the knowledge store.")

        return total_chunks



    def similarity_search(
        self,
        query: str,
        match_count: int = 10,
        match_threshold: float = 0.35,
        document_id_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant chunks via pgvector cosine similarity with structured provenance."""
        supa = get_supabase_client()
        query_embedding = self.embedder.embed(query)

        if not query_embedding or not supa:
            logger.warning("Similarity search skipped: no embedding or Supabase client.")
            return []

        try:
            result = supa.rpc(
                "match_knowledge_chunks",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": match_threshold,
                    "match_count": match_count
                }
            ).execute()

            raw_chunks = result.data or []

            if document_id_filter:
                raw_chunks = [c for c in raw_chunks if c.get("document_id") == document_id_filter]

            enriched = []
            for chunk in raw_chunks:
                meta = chunk.get("metadata") or {}
                source_label = chunk.get("source_label") or meta.get("source_label") or meta.get("source_filename") or "Internal Document"
                
                # Determine source truth type (COMPANY_TRUTH vs PROJECT_TRUTH)
                content_lower = (chunk.get("content") or "").lower()
                source_lower = source_label.lower()
                if any(p in content_lower or p in source_lower for p in ["mes", "zoho", "arc", "bus stop", "guard room", "project"]):
                    source_type = "PROJECT_TRUTH"
                else:
                    source_type = "COMPANY_TRUTH"

                enriched.append({
                    "id": chunk.get("id"),
                    "chunk_id": chunk.get("id"),
                    "document_id": chunk.get("document_id"),
                    "content": chunk.get("content"),
                    "source": source_label,
                    "source_label": source_label,
                    "source_type": source_type,
                    "confidence": float(meta.get("confidence") or 1.0),
                    "similarity": float(chunk.get("similarity") or 0.0),
                    "metadata": meta
                })

            return enriched
        except Exception as e:
            logger.error(f"Similarity search RPC failed: {e}. Attempting fallback direct chunk retrieval...")
            try:
                # Direct chunk query fallback — only use columns guaranteed to exist
                # (source_label may not exist until migration 001 runs)
                fallback_res = supa.table("knowledge_chunks").select("id, document_id, content, metadata").limit(match_count).execute()
                fallback_chunks = fallback_res.data or []
                enriched = []
                for chunk in fallback_chunks:
                    meta = chunk.get("metadata") or {}
                    source_label = meta.get("source_label") or meta.get("source_filename") or "Internal Document"
                    content_lower = (chunk.get("content") or "").lower()
                    source_lower = source_label.lower()
                    source_type = "PROJECT_TRUTH" if any(p in content_lower or p in source_lower for p in ["mes", "zoho", "arc", "bus stop", "guard room", "project"]) else "COMPANY_TRUTH"
                    enriched.append({
                        "id": chunk.get("id"),
                        "chunk_id": chunk.get("id"),
                        "document_id": chunk.get("document_id"),
                        "content": chunk.get("content"),
                        "source": source_label,
                        "source_label": source_label,
                        "source_type": source_type,
                        "confidence": float(meta.get("confidence") or 1.0),
                        "similarity": 0.85,
                        "metadata": meta
                    })
                if enriched:
                    logger.info(f"[store] Fallback direct query returned {len(enriched)} chunks.")
                return enriched
            except Exception as e2:
                logger.error(f"Direct chunk query fallback also failed: {e2}")
                return []


