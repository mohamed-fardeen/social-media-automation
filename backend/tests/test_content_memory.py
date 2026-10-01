"""
Unit tests for Content Memory and Repetition Detection.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.schemas.editorial import ContentMemoryItem
from app.services.content_intelligence.memory import check_topic_repetition, retrieve_content_memory, _cosine_similarity, _token_jaccard


def test_cosine_similarity():
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]
    assert pytest.approx(_cosine_similarity(v1, v2), 0.001) == 1.0
    assert pytest.approx(_cosine_similarity(v1, v3), 0.001) == 0.0


def test_repetition_detection_thermal_lattice_cluster():
    """
    Verifies that the historical duplicate topic cluster (thermal bridge / lattice toolpaths)
    is detected and flagged.
    """
    memory_items = [
        ContentMemoryItem(
            id="draft_001",
            topic="Thermal Bridge Elimination in 3DCP",
            angle="Thermal bridge elimination using lattice toolpaths",
            similarity_score=0.91
        ),
        ContentMemoryItem(
            id="draft_002",
            topic="Lattice Toolpaths for Insulation",
            angle="Lattice infill toolpathing for thermal performance",
            similarity_score=0.88
        )
    ]

    is_rep, max_sim, reasons = check_topic_repetition(
        candidate_topic="Thermal bridge elimination using lattice toolpaths",
        candidate_angle="How toolpath optimization prevents thermal bridging in exterior walls",
        memory_items=memory_items,
        similarity_threshold=0.80
    )

    assert is_rep is True
    assert max_sim >= 0.88
    assert len(reasons) > 0


def test_novel_topic_passes_repetition_check():
    memory_items = [
        ContentMemoryItem(
            id="draft_001",
            topic="Thermal Bridge Elimination",
            angle="Lattice toolpathing",
            similarity_score=0.20
        )
    ]

    is_rep, max_sim, reasons = check_topic_repetition(
        candidate_topic="Geopolymer curing kinetics in extreme ambient temperatures",
        candidate_angle="Cold weather setting time acceleration for polar printers",
        memory_items=memory_items,
        similarity_threshold=0.80
    )

    assert is_rep is False
    assert max_sim < 0.50
