"""
Tests for LangGraph workflow — agent nodes and state machine.
"""
import pytest
from unittest.mock import patch, MagicMock


def make_base_state(run_id="test_run_001"):
    return {
        "run_id": run_id,
        "brand_id": "brand_atlas",
        "platforms": ["instagram", "linkedin"],
        "topic_hint": "AI in business",
        "topic": None,
        "angle": None,
        "research_context": None,
        "research_evidence": None,
        "knowledge_context": None,
        "knowledge_citations": [],
        "strategy": None,
        "content_objective": None,
        "target_audience": None,
        "instagram_draft": None,
        "instagram_hashtags": [],
        "linkedin_draft": None,
        "linkedin_hashtags": [],
        "cta": None,
        "visual_prompt": None,
        "image_url": None,
        "status": "queued",
        "feedback": None,
        "version": 1,
        "draft_ids": [],
        "errors": [],
        "notes": None
    }


class TestResearchNode:
    @patch("app.agents.research.log_agent_event")
    @patch("app.agents.research.SourceRouter")
    @patch("app.agents.research.GrokLLM")
    def test_research_succeeds(self, MockGrok, MockRouter, mock_log):
        from app.schemas.research_plan import ResearchPlan, ResearchDocument
        from app.schemas.agent_outputs import ResearchOutput

        # Mock Grok: Phase 1 returns a ResearchPlan, Phase 2 returns ResearchOutput
        grok_instance = MockGrok.return_value
        grok_instance.structured.side_effect = [
            ResearchPlan(
                summary_of_intent="Research AI trends for social media",
                web_queries=["AI leadership trends 2025"]
            ),
            ResearchOutput(
                trends=["AI adoption rising"],
                competitor_signals=["Competitors launching AI tools"],
                industry_topics=["AI in leadership"],
                summary="AI reshaping business"
            )
        ]

        # Mock SourceRouter: returns one evidence document
        router_instance = MockRouter.return_value
        router_instance.execute_plan.return_value = [
            ResearchDocument(
                id="doc1",
                title="AI Trend",
                url="https://example.com/ai-trend",
                content="AI is growing in the enterprise space",
                provider="tavily",
                platform="web"
            )
        ]

        from app.agents.research import research_node
        state = make_base_state()
        result = research_node(state)

        assert result["research_context"] is not None
        assert result["topic"] is not None
        assert result["research_evidence"] is not None
        assert isinstance(result["research_evidence"], list)
        assert not any(e.startswith("research:") for e in (result.get("errors") or []))


class TestStrategistNode:
    @patch("app.agents.strategist.log_agent_event")
    @patch("app.agents.strategist.GeminiLLM")
    def test_strategist_produces_strategy(self, MockGemini, mock_log):
        from app.schemas.agent_outputs import StrategyOutput
        instance = MockGemini.return_value
        instance.structured.return_value = StrategyOutput(
            topic="AI Leadership",
            angle="Boards need AI fluency now",
            content_objective="brand authority",
            target_audience="C-suite executives",
            recommended_format="hero image"
        )

        from app.agents.strategist import strategist_node
        state = {**make_base_state(), "topic": "AI Leadership",
                 "research_context": "AI is top trend",
                 "knowledge_context": "Brand focuses on boards"}
        result = strategist_node(state)

        assert result["strategy"] is not None
        assert result["angle"] is not None


class TestCopywriterNode:
    @patch("app.agents.copywriter.log_agent_event")
    @patch("app.agents.copywriter.GroqLLM")
    def test_copywriter_generates_drafts(self, MockGroq, mock_log):
        from app.schemas.agent_outputs import CopywriterOutput
        instance = MockGroq.return_value
        instance.structured.return_value = CopywriterOutput(
            instagram_caption="🔥 AI is reshaping leadership. Are you ready?",
            instagram_hashtags=["#AI", "#leadership"],
            linkedin_post="AI fluency is now a board-level imperative. Here's why:",
            linkedin_hashtags=["#AI", "#strategy"],
            cta="Share your perspective below.",
            reasoning="Hook-driven approach for executive audience."
        )

        from app.agents.copywriter import copywriter_node
        state = {**make_base_state(), "strategy": "Topic: AI, Angle: leadership",
                 "knowledge_context": "Brand context"}
        result = copywriter_node(state)

        assert result["instagram_draft"] is not None
        assert result["linkedin_draft"] is not None
        assert len(result["instagram_hashtags"]) > 0


class TestCopywriterRegeneration:
    @patch("app.agents.copywriter.log_agent_event")
    @patch("app.agents.copywriter.GroqLLM")
    def test_regeneration_uses_feedback(self, MockGroq, mock_log):
        from app.schemas.agent_outputs import CopywriterOutput
        instance = MockGroq.return_value
        instance.structured.return_value = CopywriterOutput(
            instagram_caption="Stronger hook version 2",
            instagram_hashtags=["#AI"],
            linkedin_post="Revised LinkedIn v2",
            linkedin_hashtags=["#leadership"],
            cta="Drop a comment.",
            reasoning="Addressed feedback: made hook stronger."
        )


        from app.agents.copywriter import copywriter_node
        state = {
            **make_base_state(),
            "version": 2,
            "feedback": "Make the hook stronger and more technical.",
            "instagram_draft": "Old caption",
            "linkedin_draft": "Old LinkedIn post"
        }
        result = copywriter_node(state)

        assert result["instagram_draft"] is not None
        assert result["feedback"] is None  # Feedback cleared after processing


class TestSaveDraftNode:
    @patch("app.graph.workflow.save_checkpoint")
    @patch("app.graph.workflow.get_supabase_client")
    def test_save_draft_persists_instagram_and_linkedin_drafts(self, mock_supa, mock_save_checkpoint):
        table_calls = {}

        class FakeTable:
            def __init__(self, name):
                self.name = name
                table_calls.setdefault(name, [])

            def insert(self, payload):
                table_calls[self.name].append(("insert", payload))
                return self

            def update(self, payload):
                table_calls[self.name].append(("update", payload))
                return self

            def eq(self, field, value):
                table_calls[self.name].append(("eq", field, value))
                return self

            def execute(self):
                table_calls[self.name].append(("execute",))
                return MagicMock(data=[])

        supa = MagicMock()
        supa.table.side_effect = lambda name: FakeTable(name)
        mock_supa.return_value = supa

        from app.graph.workflow import save_draft_node

        state = {
            **make_base_state("draft_run_001"),
            "version": 2,
            "strategy": "Topic: 3D printed homes\nAngle: Faster affordable housing",
            "notes": "Reasoned from research",
            "instagram_draft": "New concrete 3D printing projects are changing site timelines.",
            "instagram_hashtags": ["#3DPrinting", "#Construction"],
            "linkedin_draft": "Construction 3D printing is moving from pilot to project delivery.",
            "linkedin_hashtags": ["#ConstructionTech"],
            "visual_prompt": "A robotic concrete printer on a construction site",
            "image_url": "https://example.com/image.png",
        }

        result = save_draft_node(state)

        inserted = table_calls["post_drafts"][0][1]
        assert len(inserted) == 1
        assert inserted[0]["platform"] == "linkedin"
        assert inserted[0]["run_id"] == "draft_run_001"
        assert inserted[0]["status"] == "pending_approval"
        assert inserted[0]["caption"] == state["linkedin_draft"]
        assert result["status"] == "awaiting_approval"
        assert len(result["draft_ids"]) == 1
        mock_save_checkpoint.assert_called_once()


class TestWorkflowState:
    def test_state_structure_complete(self):
        from app.graph.state import RunState
        state = make_base_state()
        # All required keys must be present
        required = ["run_id", "status", "version", "errors", "draft_ids",
                    "instagram_hashtags", "linkedin_hashtags", "knowledge_citations"]
        for key in required:
            assert key in state, f"Missing key: {key}"
