"""
Unit tests for Content QA, Vision QA, and Claim Grounding Gates.
"""
import pytest
from unittest.mock import patch
from app.agents.qa import evaluate_content_qa, evaluate_vision_qa, qa_node


def test_content_qa_flags_excessive_hype_or_fabrication():
    mock_qa_json = """
    {
      "accuracy_score": 4.0,
      "clarity_score": 6.0,
      "professionalism_score": 4.0,
      "conciseness_score": 5.0,
      "novelty_score": 4.0,
      "brand_fit_score": 4.0,
      "evidence_score": 3.0,
      "hook_score": 4.0,
      "naturalness_score": 4.0,
      "self_promotion_score": 2.0,
      "overall_score": 3.8,
      "decision": "REJECT",
      "issues": ["Fabricated 99.8% efficiency claim not in Editorial Brief", "Excessive hype adjectives"],
      "required_changes": ["Remove ungrounded statistics", "Tone down promotional adjectives"]
    }
    """
    with patch("app.agents.qa.GroqLLM") as MockLLM:
        mock_inst = MockLLM.return_value
        mock_inst.chat.return_value = mock_qa_json

        res = evaluate_content_qa(
            caption="Revolutionary 3D printer delivers 99.8% cost reduction instantly! Call us now!",
            editorial_brief={"topic": "3DCP", "core_message": "Precision printing", "supported_claims": [], "unsupported_claims": []}
        )

        assert res.decision == "REJECT"
        assert res.overall_score < 5.0
        assert len(res.issues) >= 1


def test_qa_node_enforces_gate():
    with patch("app.agents.qa.evaluate_content_qa") as MockContentQA, \
         patch("app.agents.qa.evaluate_vision_qa") as MockVisionQA:

        from app.schemas.editorial import ContentQAResult, VisionQAResult

        MockContentQA.return_value = ContentQAResult(
            accuracy_score=9.0, clarity_score=9.0, professionalism_score=9.0,
            conciseness_score=8.5, novelty_score=8.5, brand_fit_score=9.0,
            evidence_score=9.0, hook_score=8.5, naturalness_score=9.0,
            self_promotion_score=9.0, overall_score=8.9, decision="PASS"
        )
        MockVisionQA.return_value = VisionQAResult(
            technical_accuracy=8.5, authenticity_3dcp=9.0, concept_alignment=9.0,
            caption_alignment=8.5, machine_accuracy=8.5, composition=8.5,
            visual_clarity=9.0, brand_fit=9.0, realism=8.5, overall_score=8.7,
            decision="PASS"
        )

        state = {
            "run_id": "test_qa_001",
            "editorial_brief": {
                "topic": "Precision Extrusion",
                "core_message": "Bead control",
                "supported_claims": ["Bead geometry governs layer bonding"],
                "unsupported_claims": ["100% zero-void guarantee"]
            },
            "linkedin_draft": "Controlling bead geometry is essential for inter-layer bonding in 3D concrete printing.",
            "visual_spec": {"visual_type": "printing_process"},
            "image_url": "https://example.com/image.png",
            "version": 1
        }

        res = qa_node(state)
        assert res.get("qa_passed") is True
        assert res.get("content_qa")["decision"] == "PASS"
        assert res.get("visual_qa")["decision"] == "PASS"
