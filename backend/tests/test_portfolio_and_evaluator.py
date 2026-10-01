"""
Unit tests for Portfolio tracking and Opportunity Evaluator.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.schemas.editorial import ContentOpportunity
from app.services.content_intelligence.evaluator import evaluate_content_opportunities
from app.services.content_intelligence.portfolio import get_content_portfolio


def test_evaluate_content_opportunities_filters_weak_and_scores_strong():
    mock_opps_json = """
    {
      "opportunities": [
        {
          "topic": "Real-time acoustic sensing for concrete bead void detection",
          "relevance": 9.0,
          "novelty": 8.5,
          "evidence_strength": 9.0,
          "audience_value": 8.5,
          "specificity": 9.0,
          "brand_fit": 9.0,
          "visual_potential": 8.0,
          "credibility_risk": 2.0,
          "overall_score": 8.8,
          "reasoning": "High technical rigor with immediate application to extrusion reliability.",
          "decision": "ACCEPT"
        },
        {
          "topic": "3D printing is growing in construction",
          "relevance": 4.0,
          "novelty": 2.0,
          "evidence_strength": 3.0,
          "audience_value": 3.0,
          "specificity": 2.0,
          "brand_fit": 4.0,
          "visual_potential": 3.0,
          "credibility_risk": 7.0,
          "overall_score": 3.1,
          "reasoning": "Generic fluff without actionable engineering insights.",
          "decision": "REJECT"
        }
      ]
    }
    """
    with patch("app.services.content_intelligence.evaluator.GroqLLM") as MockLLM:
        mock_inst = MockLLM.return_value
        mock_inst.chat.return_value = mock_opps_json

        opps = evaluate_content_opportunities(
            research_context="Acoustic sensor telemetry detects void formation during mortar deposition.",
            knowledge_context="ATON robotic arm precision telemetry.",
            topic_hint="Acoustic sensing in 3DCP"
        )

        assert len(opps) == 2
        assert opps[0].decision == "ACCEPT"
        assert opps[0].overall_score >= 7.5
        assert opps[1].decision == "REJECT"
        assert opps[1].overall_score < 5.0
