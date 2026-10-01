"""
RAG and Embedding Health Validation.
Validates Gemini embedding output dimensions against database configuration (768),
verifies Supabase pgvector table, and provides runtime diagnostics.
"""
from typing import Dict, Any, Optional
from app.services.rag.embedder import EmbeddingProvider
from app.database.supabase_client import get_supabase_client
from app.config.settings import settings
from app.config.logging import logger


def validate_rag_health() -> Dict[str, Any]:
    """
    Run comprehensive health checks on RAG embedding provider and vector store.
    Returns structured diagnostic results.
    """
    results: Dict[str, Any] = {
        "status": "healthy",
        "configured_dimension": settings.EMBEDDING_DIMENSION,
        "configured_model": settings.EMBEDDING_MODEL,
        "embedding_provider_available": False,
        "embedding_test_success": False,
        "actual_embedding_dimension": None,
        "dimension_match": False,
        "supabase_available": False,
        "knowledge_chunks_count": 0,
        "match_function_healthy": False,
        "errors": []
    }

    # 1. Check Embedder
    try:
        embedder = EmbeddingProvider()
        results["embedding_provider_available"] = embedder.available
        if embedder.available:
            test_emb = embedder.embed("Kelvin6k robotic 3D concrete printing test probe")
            if test_emb and isinstance(test_emb, list):
                results["embedding_test_success"] = True
                actual_dim = len(test_emb)
                results["actual_embedding_dimension"] = actual_dim
                results["dimension_match"] = (actual_dim == settings.EMBEDDING_DIMENSION == 768)
                if not results["dimension_match"]:
                    results["status"] = "degraded"
                    results["errors"].append(
                        f"Embedding dimension mismatch: generated={actual_dim}, "
                        f"configured={settings.EMBEDDING_DIMENSION}, expected=768"
                    )
            else:
                results["status"] = "degraded"
                results["errors"].append("Embedder returned empty embedding response.")
        else:
            results["status"] = "degraded"
            results["errors"].append("GEMINI_API_KEY is not configured or embedder client failed initialization.")
    except Exception as e:
        results["status"] = "unhealthy"
        results["errors"].append(f"Embedder test raised exception: {str(e)}")

    # 2. Check Supabase & pgvector
    try:
        supa = get_supabase_client()
        results["supabase_available"] = bool(supa)
        if supa:
            # Check row count
            try:
                res = supa.table("knowledge_chunks").select("id", count="exact").limit(1).execute()
                results["knowledge_chunks_count"] = res.count or 0
            except Exception as e:
                results["errors"].append(f"Failed to query knowledge_chunks: {str(e)}")

            # Test vector match function with probe embedding
            if results["embedding_test_success"] and test_emb:
                try:
                    match_res = supa.rpc(
                        "match_knowledge_chunks",
                        {
                            "query_embedding": test_emb,
                            "match_threshold": 0.0,
                            "match_count": 1
                        }
                    ).execute()
                    results["match_function_healthy"] = True
                except Exception as e:
                    results["status"] = "degraded"
                    results["match_function_healthy"] = False
                    results["errors"].append(f"match_knowledge_chunks RPC failed: {str(e)}")
        else:
            results["errors"].append("Supabase client is not available.")
    except Exception as e:
        results["status"] = "unhealthy"
        results["errors"].append(f"Supabase check failed: {str(e)}")

    logger.info(f"[RAG Health] Status: {results['status']}, Dim: {results['actual_embedding_dimension']}/768, Chunks: {results['knowledge_chunks_count']}")
    return results
