"""
Tests for RAG — chunking, embedding, and knowledge store operations.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestChunker:
    def test_basic_chunking(self):
        from app.services.rag.chunker import RecursiveTextChunker
        chunker = RecursiveTextChunker(chunk_size=10, overlap=2)
        text = " ".join([f"word{i}" for i in range(50)])
        chunks = chunker.chunk_text(text, {"source": "test"})
        assert len(chunks) > 0
        assert all("content" in c and "metadata" in c for c in chunks)

    def test_empty_text_returns_no_chunks(self):
        from app.services.rag.chunker import RecursiveTextChunker
        chunker = RecursiveTextChunker()
        chunks = chunker.chunk_text("", {"source": "test"})
        assert chunks == []

    def test_overlap_produces_more_chunks(self):
        from app.services.rag.chunker import RecursiveTextChunker
        text = " ".join([f"word{i}" for i in range(100)])
        chunker_no_overlap = RecursiveTextChunker(chunk_size=20, overlap=0)
        chunker_with_overlap = RecursiveTextChunker(chunk_size=20, overlap=10)
        chunks_no = chunker_no_overlap.chunk_text(text, {})
        chunks_with = chunker_with_overlap.chunk_text(text, {})
        assert len(chunks_with) >= len(chunks_no)

    def test_metadata_preserved(self):
        from app.services.rag.chunker import RecursiveTextChunker
        chunker = RecursiveTextChunker(chunk_size=5, overlap=1)
        text = "one two three four five six seven eight nine ten"
        meta = {"doc_id": "abc", "source": "test_doc"}
        chunks = chunker.chunk_text(text, meta)
        for chunk in chunks:
            assert chunk["metadata"]["doc_id"] == "abc"
            assert "chunk_index" in chunk["metadata"]


class TestEmbedder:
    def test_embedder_availability(self):
        with patch("app.services.rag.embedder.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = "test_key"
            mock_settings.EMBEDDING_MODEL = "gemini-embedding-001"
            mock_settings.EMBEDDING_DIMENSION = 768
            from app.services.rag.embedder import EmbeddingProvider
            provider = EmbeddingProvider()
            assert provider is not None
            assert provider.model == "gemini-embedding-001"

    def test_embedder_returns_none_without_key(self):
        with patch("app.services.rag.embedder.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = ""
            mock_settings.EMBEDDING_MODEL = "gemini-embedding-001"
            mock_settings.EMBEDDING_DIMENSION = 768
            from app.services.rag.embedder import EmbeddingProvider
            provider = EmbeddingProvider()
            assert provider.embed("test") is None


class TestKnowledgeStore:
    def test_ingest_with_no_supabase(self):
        """Should not crash and return chunk count."""
        with patch("app.services.rag.store.get_supabase_client", return_value=None):
            with patch("app.services.rag.store.EmbeddingProvider") as MockEmbed:
                instance = MockEmbed.return_value
                instance.embed_batch.return_value = [[0.1] * 768]
                from app.services.rag.store import KnowledgeStore
                store = KnowledgeStore()
                pages = [{"page_number": 1, "content": "This is test content for ingestion.",
                          "method": "embedded_text", "confidence": 1.0, "filename": "test.pdf"}]
                count = store.ingest_pages("doc_123", pages, "test.pdf")
                assert count >= 0

    def test_ingest_raises_when_embeddings_missing(self):
        with patch("app.services.rag.store.get_supabase_client", return_value=None):
            with patch("app.services.rag.store.EmbeddingProvider") as MockEmbed:
                instance = MockEmbed.return_value
                instance.embed_batch.return_value = [None]
                from app.services.rag.store import KnowledgeStore
                store = KnowledgeStore()
                pages = [{"page_number": 1, "content": "This is test content for ingestion.",
                          "method": "embedded_text", "confidence": 1.0, "filename": "test.pdf"}]
                with pytest.raises(ValueError, match="Embedding generation failed"):
                    store.ingest_pages("doc_123", pages, "test.pdf")

    def test_similarity_search_no_supabase(self):
        with patch("app.services.rag.store.get_supabase_client", return_value=None):
            from app.services.rag.store import KnowledgeStore
            store = KnowledgeStore()
            results = store.similarity_search("AI trends")
            assert results == []
