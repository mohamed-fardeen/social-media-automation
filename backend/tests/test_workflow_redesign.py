"""
Integration and node execution tests for the redesigned LangGraph workflow.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.graph.workflow import build_graph, get_graph, start_run
from app.graph.state import RunState


def test_build_graph_contains_all_editorial_nodes():
    graph = build_graph()
    nodes = graph.nodes
    expected_nodes = [
        "init_run",
        "research",
        "knowledge",
        "content_intelligence",
        "strategist",
        "ideation",
        "await_idea_selection",
        "editorial_brief",
        "copywriter",
        "visual",
        "image_gen",
        "qa",
        "save_draft",
        "human_approval",
        "publisher"
    ]
    for n in expected_nodes:
        assert n in nodes, f"Expected node '{n}' missing from graph."


@patch("app.agents.research.log_agent_event")
@patch("app.agents.research._load_saved_research_context")
def test_draft_only_mode_uses_saved_insights_without_scraping(mock_load, mock_log):
    from app.agents.research import research_node
    mock_load.return_value = (
        "RECENT INDUSTRY RESEARCH INSIGHTS:\n- [INDUSTRY_RESEARCH] Mortar Rheology: Fast setting concrete analysis.",
        [{"id": "ins_1", "title": "Mortar Rheology", "content": "Fast setting", "source_type": "INDUSTRY_RESEARCH"}]
    )

    state = {
        "run_id": "test_draft_only_001",
        "mode": "draft_only",
        "topic_hint": "Concrete Rheology",
        "platforms": ["linkedin"],
        "brand_id": "default",
        "errors": []
    }

    res = research_node(state)
    assert res["research_context"] is not None
    assert "RECENT INDUSTRY RESEARCH INSIGHTS" in res["research_context"]
    assert len(res["research_evidence"]) == 1
    assert res["research_evidence"][0]["source_type"] == "INDUSTRY_RESEARCH"
    mock_load.assert_called_once()
