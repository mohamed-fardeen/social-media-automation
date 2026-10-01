"""
Unit tests for RAG reliability and embedding health validation.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.services.rag.health import validate_rag_health
from app.config.settings import settings


def test_embedding_dimension_is_768():
    assert settings.EMBEDDING_DIMENSION == 768
    assert settings.EMBEDDING_MODEL == "gemini-embedding-001"


def test_rag_health_validation():
    with patch("app.services.rag.health.EmbeddingProvider") as MockEmbedder, \
         patch("app.services.rag.health.get_supabase_client") as MockSupa:

        embed_inst = MockEmbedder.return_value
        embed_inst.available = True
        embed_inst.embed.return_value = [0.01] * 768

        supa_inst = MockSupa.return_value
        table_mock = MagicMock()
        table_mock.select.return_value.limit.return_value.execute.return_value.count = 42
        supa_inst.table.return_value = table_mock
        supa_inst.rpc.return_value.execute.return_value.data = [{"id": "1", "similarity": 0.95}]

        health = validate_rag_health()
        assert health["status"] == "healthy"
        assert health["actual_embedding_dimension"] == 768
        assert health["dimension_match"] is True
        assert health["embedding_test_success"] is True
        assert health["match_function_healthy"] is True
