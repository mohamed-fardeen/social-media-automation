"""
Unit tests for Editorial Brief generation and claim grounding.
"""
import pytest
from unittest.mock import patch
from app.agents.editorial_brief import editorial_brief_node
from app.schemas.editorial import EditorialBrief


def test_editorial_brief_node_constructs_valid_brief():
    mock_brief_json = """
    {
      "topic": "Polar vs Gantry Robotics in 3D Concrete Printing",
      "core_message": "Polar robotic kinematics reduce on-site footprint and transportation volume compared to rigid gantry systems.",
      "why_it_matters": "Enables rapid mobilization and off-site/on-site flexibility for infrastructure projects.",
      "target_audience": "Civil engineers, equipment managers, and contractors",
      "evidence": [{"claim": "ATOM polar setup fits on a standard flatbed", "source": "Kelvin6k Spec Sheet", "source_type": "COMPANY_TRUTH"}],
      "kelvin6k_connection": "Demonstrated by ATOM polar printer and ATON 6-axis arm.",
      "proof_level": "lab_proven",
      "supported_claims": [
        "Polar systems have a smaller transport footprint than 3-axis gantry frames",
        "Continuous rotary printing eliminates corner travel dead-time"
      ],
      "unsupported_claims": [
        "Gantry printers are completely obsolete for all building types"
      ],
      "tone": "Authoritative, concise, engineering-focused B2B",
      "content_type": "comparison",
      "format": "comparison",
      "cta": "How do you evaluate kinematics vs build envelope on your jobsites?",
      "visual_story": "Side-by-side technical diagram showing polar rotation envelope vs gantry frame boundary.",
      "visual_type": "technical_diagram",
      "visual_requirements": ["Clean vector lines", "Accurate rotary reach envelope"],
      "visual_negatives": ["No sci-fi neon colors", "No generic illustrations"]
    }
    """
    with patch("app.agents.editorial_brief.GroqLLM") as MockLLM:
        mock_inst = MockLLM.return_value
        mock_inst.chat.return_value = mock_brief_json

        state = {
            "run_id": "test_brief_001",
            "current_idea_index": 1,
            "ideas": [
                {
                    "index": 1,
                    "headline": "Polar vs Gantry Robotics in 3DCP",
                    "angle": "Polar kinematics reduce on-site footprint",
                    "format": "comparison",
                    "summary": "Why polar printers offer mobility advantages",
                    "image_hint": "Side-by-side diagram"
                }
            ],
            "research_context": "Comparative kinematic studies.",
            "knowledge_context": "[COMPANY_TRUTH] ATOM polar printer specifications.",
            "brand_id": "default",
            "errors": []
        }

        result = editorial_brief_node(state)
        brief = result.get("editorial_brief")

        assert brief is not None
        assert brief["topic"] == "Polar vs Gantry Robotics in 3D Concrete Printing"
        assert len(brief["supported_claims"]) == 2
        assert len(brief["unsupported_claims"]) == 1
        assert brief["visual_type"] == "technical_diagram"
        assert len(result.get("claim_evidence") or []) == 2
