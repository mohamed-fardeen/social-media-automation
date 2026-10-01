"""
Unit tests for Copywriter and Visual Director.
"""
import pytest
from unittest.mock import patch
from app.agents.copywriter import copywriter_node
from app.agents.visual import visual_node
from app.schemas.agent_outputs import CopywriterOutput
from app.schemas.editorial import VisualSpecification


def test_copywriter_produces_clean_evidence_grounded_post():
    mock_copy = CopywriterOutput(
        instagram_caption="Robotic arm reach envelopes dictate build geometry.",
        instagram_hashtags=["#3DConcretePrinting", "#Robotics"],
        linkedin_post=(
            "When designing for 3D concrete printing, machine kinematics determine structural freedom.\n\n"
            "While gantry systems provide large rectangular envelopes, articulated 6-axis arms like ATON "
            "allow variable nozzle orientation and complex toolpaths without continuous scaffolding.\n\n"
            "What kinematics model best fits your target build geometries?"
        ),
        linkedin_hashtags=["#3DConcretePrinting", "#ConstructionRobotics", "#CivilEngineering"],
        cta="What kinematics model best fits your target build geometries?",
        reasoning="Focused on kinematics comparison without hyperbolic buzzwords.",
        supported_claims=["Articulated arms allow variable nozzle orientation"],
        unsupported_claims=[]
    )

    with patch("app.agents.copywriter.GroqLLM") as MockLLM:
        mock_inst = MockLLM.return_value
        mock_inst.structured.return_value = mock_copy

        state = {
            "run_id": "test_copy_001",
            "editorial_brief": {
                "topic": "Robotic Kinematics in 3DCP",
                "core_message": "Articulated arms provide multi-axis extrusion control.",
                "why_it_matters": "Enables complex parametric geometry.",
                "kelvin6k_connection": "Demonstrated with ATON.",
                "supported_claims": ["Articulated arms allow variable nozzle orientation"],
                "unsupported_claims": [],
                "tone": "Authoritative, concise, engineering-focused B2B",
                "format": "technical_breakdown"
            },
            "version": 1,
            "feedback": None
        }

        res = copywriter_node(state)
        draft = res.get("linkedin_draft") or ""
        assert len(draft) > 50
        assert "revolutionary" not in draft.lower()
        assert "game-changing" not in draft.lower()
        assert len(res.get("linkedin_hashtags") or []) >= 2


def test_visual_director_produces_grounded_spec():
    mock_visual_json = """
    {
      "subject": "6-axis robotic arm concrete extrusion",
      "visual_type": "printing_process",
      "core_understanding": "Articulated nozzle depositing curved mortar bead",
      "physical_demonstration": "Active extrusion printhead on hardened horizontal layer striations",
      "key_elements_visible": ["Extruder nozzle", "Wet concrete bead", "Horizontal striations"],
      "elements_not_visible": ["Smooth drywall", "Neon CGI", "Sci-fi robots"],
      "is_3dcp_relevant": true,
      "authenticity_details": ["Distinct 25mm layer ridges", "Matte mortar texture"],
      "machine_reference": "aton",
      "image_prompt": "Industrial 6-axis robotic arm concrete printer actively extruding a precise mortar bead onto a curved architectural wall with clear horizontal layer lines.",
      "aspect_ratio": "1:1",
      "is_text_only": false
    }
    """
    with patch("app.agents.visual.GeminiLLM") as MockLLM:
        mock_inst = MockLLM.return_value
        mock_inst.chat.return_value = mock_visual_json

        state = {
            "run_id": "test_vis_001",
            "editorial_brief": {
                "topic": "ATON Robotic Arm Precision",
                "core_message": "Multi-axis deposition control",
                "visual_story": "Robotic arm printing curved facade",
                "visual_type": "printing_process",
                "visual_requirements": ["Horizontal bead ridges", "Matte texture"],
                "visual_negatives": ["No smooth drywall"]
            },
            "image_mode": "with_image"
        }

        res = visual_node(state)
        spec = res.get("visual_spec")
        assert spec is not None
        assert spec["visual_type"] == "printing_process"
        assert res.get("referenced_product") == "aton"
        assert "extruded" in res.get("visual_prompt").lower() or "layer" in res.get("visual_prompt").lower()


def test_gemini_image_provider_handles_none_content_gracefully():
    from unittest.mock import MagicMock
    from app.services.image.generator import GeminiImageProvider

    provider = GeminiImageProvider(model_name="gemini-3.6-flash")
    provider.available = True
    provider.client = MagicMock()

    # Case 1: Empty candidates
    mock_resp_empty = MagicMock()
    mock_resp_empty.candidates = []
    mock_resp_empty.prompt_feedback = "BLOCK_SAFETY"
    provider.client.models.generate_content.return_value = mock_resp_empty

    result = provider.generate("test prompt", reference_image_bytes=b"fake_image_bytes")
    assert result is None

    # Case 2: Candidate with content=None (e.g. safety block)
    mock_resp_none_content = MagicMock()
    mock_candidate = MagicMock()
    mock_candidate.content = None
    mock_candidate.finish_reason = "SAFETY"
    mock_candidate.safety_ratings = [{"category": "HARM_CATEGORY_DANGEROUS", "probability": "HIGH"}]
    mock_resp_none_content.candidates = [mock_candidate]
    provider.client.models.generate_content.return_value = mock_resp_none_content

    result = provider.generate("test prompt", reference_image_bytes=b"fake_image_bytes")
    assert result is None

    # Case 3: Candidate with content.parts=None
    mock_resp_none_parts = MagicMock()
    mock_candidate_parts_none = MagicMock()
    mock_candidate_parts_none.content.parts = None
    mock_candidate_parts_none.finish_reason = "RECITATION"
    mock_resp_none_parts.candidates = [mock_candidate_parts_none]
    provider.client.models.generate_content.return_value = mock_resp_none_parts

    result = provider.generate("test prompt", reference_image_bytes=b"fake_image_bytes")
    assert result is None

    # Case 4: Candidate with valid inline_data
    mock_resp_valid = MagicMock()
    mock_candidate_valid = MagicMock()
    mock_part = MagicMock()
    mock_part.inline_data.data = b"generated_png_bytes"
    mock_candidate_valid.content.parts = [mock_part]
    mock_resp_valid.candidates = [mock_candidate_valid]
    provider.client.models.generate_content.return_value = mock_resp_valid

    result = provider.generate("test prompt", reference_image_bytes=b"fake_image_bytes")
    assert result == b"generated_png_bytes"


def test_gemini_image_provider_imagen3():
    from unittest.mock import MagicMock
    from app.services.image.generator import GeminiImageProvider

    provider = GeminiImageProvider(model_name="imagen-3.0-generate-002")
    provider.available = True
    provider.client = MagicMock()

    mock_resp = MagicMock()
    mock_img = MagicMock()
    mock_img.image.image_bytes = b"imagen_jpeg_bytes"
    mock_resp.generated_images = [mock_img]
    provider.client.models.generate_images.return_value = mock_resp

    result = provider.generate("Industrial 3D printer building structure")
    assert result == b"imagen_jpeg_bytes"
    provider.client.models.generate_images.assert_called_once()


def test_gemini_web_bridge_decodes_image_response(monkeypatch):
    import base64
    from unittest.mock import MagicMock
    from app.services.image.generator import GeminiWebBridgeProvider

    provider = GeminiWebBridgeProvider()
    provider.bridge_url = "http://127.0.0.1:8765/generate"
    provider.available = True
    response = MagicMock()
    response.headers = {"content-type": "application/json"}
    response.json.return_value = {"image_base64": base64.b64encode(b"bridge_image").decode("ascii")}

    with patch("httpx.post", return_value=response) as post:
        assert provider.generate("A grounded robotic concrete printer") == b"bridge_image"

    assert post.call_args.kwargs["json"]["prompt"] == "A grounded robotic concrete printer"


def test_image_generation_waterfall_order():
    from app.services.image.generator import GeminiImageProvider, CloudflareImageProvider, DALLEImageProvider, StubImageProvider
    from app.config.settings import settings

    # Verify Gemini image models default list
    gemini_models = [
        "gemini-3.1-flash-image",
        "gemini-3-pro-image-preview",
        "gemini-2.5-flash-image"
    ]
    providers = [GeminiImageProvider(model_name=m) for m in gemini_models]
    if settings.CF_ACCOUNT_ID and settings.CF_API_TOKEN:
        providers.append(CloudflareImageProvider())

    model_sequence = [p.model_name if isinstance(p, GeminiImageProvider) else type(p).__name__ for p in providers]
    assert model_sequence[0] == "gemini-3.1-flash-image"
    assert model_sequence[1] == "gemini-3-pro-image-preview"
    assert model_sequence[2] == "gemini-2.5-flash-image"
    if settings.CF_ACCOUNT_ID and settings.CF_API_TOKEN:
        assert model_sequence[3] == "CloudflareImageProvider"



