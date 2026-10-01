"""
Editorial Brief Agent / Node.
Constructs the authoritative single source of truth (EditorialBrief)
after human idea selection to guide Copywriting and Visual Direction.
"""
import json
import re
import time
from typing import Dict, Any, List, Optional
from app.graph.state import RunState
from app.agents.log_helper import log_agent_event
from app.schemas.editorial import EditorialBrief, ClaimEvidenceItem
from app.services.llm.groq import GroqLLM
from app.services.brand_profile import get_brand_profile, format_brand_context
from app.config.logging import logger


EDITORIAL_BRIEF_SYSTEM_PROMPT = """You are the Executive Managing Editor for Kelvin6k (robotic 3D concrete printing).
Your job is to synthesize the APPROVED idea, verified evidence, brand knowledge, and constraints into a single authoritative EDITORIAL BRIEF.

This brief is the sole source of truth for both the Copywriter and the Visual Director.
Downstream agents must NOT reinterpret the raw research independently.

RULES:
1. STRICT CLAIM GROUNDING (ZERO HALLUCINATION):
   - Identify which factual assertions are explicitly SUPPORTED by the research or brand knowledge (`supported_claims`).
   - Identify claims that are speculative, ungrounded, or unsupported by evidence and MUST NOT be asserted (`unsupported_claims`).
   - NEVER fabricate numbers, performance percentages, or project results.
   - Any claim about product features, technical capabilities (like telemetry or solar power), or awards MUST be rejected to the `unsupported_claims` array unless specifically found in the provided VERIFIED BRAND KNOWLEDGE.
   - If the APPROVED IDEA contains hallucinated features or fake awards, strip them out before writing the `supported_claims`.
2. PROFESSIONAL B2B EDITORIAL TONE:
   - Voice must match serious construction-technology leaders (e.g. COBOD, PERI, CyBe, Tvasta, ICON).
   - Tone: Authoritative, clear, engineering-dense, and credible without generic marketing hype or artificial AI phrases.
3. CLEAR VISUAL STORY:
   - Define the exact physical mechanism, toolpath, machine, structure, or result that visually proves the post's core message.
   - Choose the appropriate `visual_type` (e.g. printing_process, technical_diagram, architectural_photography, engineering_cutaway, machine_photography, or text_only).
   - List mandatory visual requirements and explicit negatives (e.g. no smooth drywall, no CGI gloss, no neon sci-fi).

Return structured JSON matching the EditorialBrief schema:
{
  "topic": "...",
  "core_message": "...",
  "why_it_matters": "...",
  "target_audience": "Structural engineers, general contractors, robotics researchers",
  "evidence": [{"claim": "...", "source": "...", "source_type": "INDUSTRY_RESEARCH|COMPANY_TRUTH|PROJECT_TRUTH"}],
  "kelvin6k_connection": "...",
  "proof_level": "verified_project|lab_proven|industry_benchmark|strategic_perspective",
  "supported_claims": ["..."],
  "unsupported_claims": ["..."],
  "tone": "Authoritative, concise, engineering-focused B2B",
  "content_type": "technical_insight|project_story|comparison|educational",
  "format": "technical_breakdown|data_snack|case_study|carousel|founder_pov",
  "cta": "...",
  "visual_story": "...",
  "visual_type": "real_project_photography|machine_photography|printing_process|engineering_cutaway|technical_diagram|before_after|comparison|product_visualization|conceptual_visualization|architectural_photography|text_only",
  "visual_requirements": ["..."],
  "visual_negatives": ["..."]
}
"""


def editorial_brief_node(state: RunState) -> RunState:
    """
    Constructs the EditorialBrief after an idea has been chosen by the user.
    """
    run_id = state["run_id"]
    log_id = log_agent_event(run_id, "editorial_brief", "running",
                             input_summary=f"Assembling brief for idea: {state.get('current_idea_index', 1)}")
    t0 = time.monotonic()

    # Determine the selected idea
    idea_index = state.get("current_idea_index") or 1
    ideas = state.get("ideas") or []
    selected_idea = next((i for i in ideas if i.get("index") == idea_index), None)
    if not selected_idea and ideas:
        selected_idea = ideas[0]

    headline = (selected_idea or {}).get("headline") or state.get("topic_hint") or "3D Concrete Printing"
    angle = (selected_idea or {}).get("angle") or state.get("angle") or ""
    summary = (selected_idea or {}).get("summary") or ""
    fmt = (selected_idea or {}).get("format") or state.get("format") or "technical_breakdown"
    image_hint = (selected_idea or {}).get("image_hint") or state.get("image_hint") or ""
    image_mode = state.get("image_mode") or "with_image"

    try:
        profile = get_brand_profile(state.get("brand_id") or "default") or {}
        brand_context = format_brand_context(profile, focus_topic=state.get("topic_hint"))

        user_prompt = f"""
=== APPROVED IDEA ===
Headline: {headline}
Angle: {angle}
Summary: {summary}
Format: {fmt}
Visual Hint: {image_hint}
Image Mode: {image_mode}

=== RESEARCH EVIDENCE ===
{(state.get('research_context') or 'No external research available.')[:2500]}

=== VERIFIED BRAND KNOWLEDGE ===
{(state.get('knowledge_context') or 'No brand knowledge available.')[:1500]}

=== BRAND CONSTRAINTS ===
{brand_context[:1000]}

Create the authoritative EditorialBrief JSON now.
"""

        llm = GroqLLM()
        brief = None

        # Attempt 1: Groq Structured Output (JSON mode)
        for attempt in range(2):
            try:
                struct_res = llm.structured(
                    system_prompt=EDITORIAL_BRIEF_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    schema=EditorialBrief,
                    temperature=0.2
                )
                if struct_res and isinstance(struct_res, EditorialBrief):
                    brief = struct_res
                    logger.info(f"[editorial_brief_node] Run {run_id}: Successfully built brief via structured output (attempt {attempt+1}).")
                    break
            except Exception as struct_err:
                logger.warning(f"[editorial_brief_node] Structured output attempt {attempt+1} failed: {struct_err}")

        # Attempt 2: Gemini failover if Groq failed
        if not brief:
            try:
                from app.services.llm.gemini import GeminiLLM
                gemini_llm = GeminiLLM()
                raw = gemini_llm.chat(
                    system_prompt=EDITORIAL_BRIEF_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    temperature=0.2,
                )
                raw_clean = re.sub(r"```json\s*|\s*```", "", raw).strip()
                parsed = json.loads(raw_clean)
                brief = EditorialBrief(**parsed)
                logger.info(f"[editorial_brief_node] Run {run_id}: Successfully built brief via Gemini failover.")
            except Exception as gemini_err:
                logger.warning(f"[editorial_brief_node] Gemini failover also failed: {gemini_err}")

        if not brief:
            raise RuntimeError("All LLM attempts to generate valid EditorialBrief failed.")

        # Enforce text_only visual_type if image_mode is text_only or image_hint is empty in mix mode
        if image_mode == "text_only" or (image_mode == "mix" and not image_hint):
            brief.visual_type = "text_only"

        brief_dict = brief.model_dump()
        claim_items = [
            ClaimEvidenceItem(
                statement=claim,
                claim_type="SUPPORTED_CLAIM",
                source_type="COMPANY_TRUTH" if "kelvin" in claim.lower() else "INDUSTRY_RESEARCH",
                supported=True
            ).model_dump()
            for claim in brief.supported_claims
        ]

        latency = int((time.monotonic() - t0) * 1000)
        log_agent_event(run_id, "editorial_brief", "complete",
                        output_summary=f"Editorial Brief compiled ({len(brief.supported_claims)} supported claims)",
                        latency_ms=latency,
                        log_id=log_id)

        return {
            **state,
            "editorial_brief": brief_dict,
            "claim_evidence": claim_items,
            "format": brief.format,
            "angle": brief.core_message,
            "status": "writing"
        }

    except Exception as e:
        logger.error(f"[editorial_brief_node] [FALLBACK ACTIVE] Failed for run {run_id}: {e}")
        log_agent_event(run_id, "editorial_brief", "error", error=str(e), log_id=log_id)

        # Fallback brief
        fallback_brief = EditorialBrief(
            topic=headline,
            core_message=angle or headline,
            why_it_matters=summary or "Optimizing construction efficiency and structural performance.",
            target_audience="Structural engineers, contractors, robotics researchers",
            evidence=[],
            kelvin6k_connection="Kelvin6k robotic printing capabilities.",
            proof_level="industry_benchmark",
            supported_claims=[angle or headline],
            unsupported_claims=[],
            tone="Authoritative, concise, engineering-focused B2B",
            content_type="technical_insight",
            format=fmt,
            cta="",
            visual_story=image_hint or "Clear architectural photograph of 3D-printed concrete structure.",
            visual_type="text_only" if image_mode == "text_only" else "architectural_photography",
            visual_requirements=["Horizontal bead layer lines", "Authentic matte mortar texture"],
            visual_negatives=["No smooth drywall", "No CGI gloss"]
        )

        degraded = state.get("degraded_steps") or []
        if "editorial_brief_fallback" not in degraded:
            degraded.append("editorial_brief_fallback")

        return {
            **state,
            "editorial_brief": fallback_brief.model_dump(),
            "claim_evidence": [],
            "format": fmt,
            "angle": fallback_brief.core_message,
            "degraded_steps": degraded,
            "errors": state.get("errors", []) + [f"editorial_brief_fallback: {e}"],
            "status": "writing"
        }
