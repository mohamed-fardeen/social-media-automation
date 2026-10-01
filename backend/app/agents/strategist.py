"""
Strategist Agent — synthesizes content opportunities, content memory, portfolio balance,
and brand profile to select the optimal strategic insight and generate 3 genuinely distinct
communicative angles (Technical Insight, Project Connection, Industry Implication, Comparison, Educational).
"""
import json
import re
import time
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.graph.state import RunState
from app.agents.log_helper import log_agent_event
from app.services.llm.gemini import GeminiLLM
from app.services.llm.groq import GroqLLM
from app.services.brand_profile import get_brand_profile, format_brand_context
from app.database.supabase_client import get_supabase_client
from app.config.logging import logger


def _update_run_progress(run_id: str, status: str, agent: str) -> None:
    try:
        from app.database.supabase_client import get_supabase_client
        supa = get_supabase_client()
        if supa:
            supa.table("post_runs").update(
                {"status": status, "current_agent": agent}
            ).eq("id", run_id).execute()
    except Exception:
        pass


STRATEGIST_SYSTEM_PROMPT = """You are the Chief Content Strategist for Kelvin6k (a leader in construction 3D printing and robotic concrete automation).
You receive:
1. ALL Validated Content Opportunities (up to 3, each on a DIFFERENT topic, scored by Content Intelligence).
2. Content Memory & Portfolio (to avoid repetitive angles and ensure category balance).
3. Real Research Evidence (with source attribution).
4. Verified Brand Knowledge (products: ATON, ATOM V1/V2, G.MINI, ARCUS; projects: MES, ZOHO, GCC bus-stop, THE ARC).
5. Recent Idea Headlines (the headlines and angles from the last 10 generated drafts).

YOUR CORE RESPONSIBILITIES:
1. Review ALL provided Validated Content Opportunities — they cover DIFFERENT topics.
2. Generate EXACTLY ONE IDEA per opportunity (up to 3 ideas total), where each idea covers a genuinely different subject.
   - Idea 1 → Based on Opportunity 1's topic and evidence
   - Idea 2 → Based on Opportunity 2's topic and evidence (MUST be on a different subject than Idea 1)
   - Idea 3 → Based on Opportunity 3's topic and evidence (MUST be on a different subject than Ideas 1 & 2)
3. The overall strategy.topic should reflect the BEST single opportunity selected as the primary.

CRITICAL DIVERSITY RULES (MANDATORY — VIOLATIONS ARE FAILURES):
- Each idea MUST cover a distinct research topic. DO NOT generate 3 angles on the same subject.
- Each idea must have a headline, angle, and evidence that are UNIQUE across all 3 ideas.
- If opportunities are about different technologies (e.g. digital twin vs defect detection vs a project case study), each idea must reflect that different technology.

DE-DUPLICATION REQUIREMENT (MANDATORY):
You are given `recent_idea_headlines` — a list of headlines and angles from the last 10 drafts.
- Never output an idea with the same headline, angle, or core mechanism as one already present in `recent_idea_headlines`.
- If the research does not support 3 non-duplicate ideas, generate fewer and set `insufficient_novel_angles: true`.

STRICT FACTUAL GROUNDING (CRITICAL — HALLUCINATION = AUTOMATIC FAILURE):
- NEVER invent or exaggerate statistics, numbers, percentages, or timeline dates unless they appear VERBATIM in the provided Research Evidence or Verified Brand Knowledge.
- NEVER fabricate project results, machine capabilities, or competitor claims.
- If a specific statistic (e.g. "<5% error", "30% rework reduction") is not directly present in the evidence, you MUST NOT include it. Use qualitative language instead (e.g. "significant reduction").
- Every claim must be directly traceable to the provided research evidence or verified brand knowledge.

BRAND GROUNDING REQUIREMENT:
- Every idea MUST explicitly mention a Kelvin6k product (ATON, ATOM, G.MINI, ARCUS) or a verified project (MES, GCC Bus-Stop, ZOHO, THE ARC) in the kelvin6k_connection field.
- If the research does not connect naturally to a specific product, use the most contextually relevant one and explain how.
- Posts that don't mention Kelvin6k's actual machines or projects are NOT acceptable for a B2B brand content strategy.

IDEA STRUCTURE (per idea):
- index (1..3)
- format (slug: data_snack | comparison | case_study | carousel | founder_pov | technical_breakdown | contrarian)
- format_label (reader label, e.g. "Engineering Breakdown", "Project Benchmark", "Tech Comparison")
- headline (<= 80 chars, punchy, concrete — must reflect THIS idea's unique topic)
- angle (1 precise sentence explaining the argument — must be unique to THIS idea's topic)
- summary (why the reader stops scrolling)
- why_reader_cares (concrete value for civil engineers, contractors, roboticists)
- kelvin6k_connection (MUST name a specific Kelvin6k product or verified project)
- evidence_strength (High/Medium)
- novelty (High/Medium)
- visual_potential (High/Medium)
- image_hint (specific visual concept for ONE image; empty string if text_only)

Return JSON:
{
  "strategy": {
    "topic": "...",
    "angle": "...",
    "content_objective": "...",
    "target_audience": "Structural engineers, general contractors, robotics researchers",
    "recommended_format": "technical_breakdown"
  },
  "insufficient_novel_angles": false,
  "ideas": [
    {
      "index": 1,
      "format": "technical_breakdown",
      "format_label": "Engineering Deep Dive",
      "headline": "...",
      "angle": "...",
      "summary": "...",
      "why_reader_cares": "...",
      "kelvin6k_connection": "ATON robot / GCC Bus-Stop project / etc.",
      "evidence_strength": "High",
      "novelty": "High",
      "visual_potential": "High",
      "image_hint": "..."
    },
    { "index": 2, "headline": "DIFFERENT TOPIC than idea 1...", ... },
    { "index": 3, "headline": "DIFFERENT TOPIC than ideas 1 and 2...", ... }
  ]
}"""


def _get_recent_idea_headlines(limit: int = 10) -> List[str]:
    """Query the last 10 drafts and runs to extract recent headlines and angles for de-duplication."""
    recent_items: List[str] = []
    seen = set()
    try:
        supa = get_supabase_client()
        if supa:
            # Query recent post_drafts
            draft_res = supa.table("post_drafts") \
                .select("format_label, strategy, reasoning, caption, created_at") \
                .order("created_at", desc=True) \
                .limit(limit) \
                .execute()
            for r in (draft_res.data or []):
                reasoning = (r.get("reasoning") or "").strip()
                caption = (r.get("caption") or "").strip()
                label = (r.get("format_label") or "").strip()
                first_line = caption.split("\n")[0][:90] if caption else ""
                key = f"{label}::{reasoning}"
                if key not in seen and (label or reasoning or first_line):
                    seen.add(key)
                    recent_items.append(f"- Headline/Topic: {label or first_line} | Angle: {reasoning}")

            # Query recent post_runs ideas if we have fewer than limit
            if len(recent_items) < limit:
                run_res = supa.table("post_runs") \
                    .select("ideas, created_at") \
                    .order("created_at", desc=True) \
                    .limit(limit) \
                    .execute()
                for r in (run_res.data or []):
                    for idea in (r.get("ideas") or []):
                        h = (idea.get("headline") or "").strip()
                        a = (idea.get("angle") or "").strip()
                        key = f"{h}::{a}"
                        if h and key not in seen:
                            seen.add(key)
                            recent_items.append(f"- Headline: {h} | Angle: {a}")
                        if len(recent_items) >= limit:
                            break
                    if len(recent_items) >= limit:
                        break
    except Exception as e:
        logger.warning(f"[strategist_node] Failed to query recent idea headlines: {e}")

    return recent_items[:limit]


class StrategistIdea(BaseModel):
    index: int = 1
    format: str = "technical_breakdown"
    format_label: str = "Engineering Deep Dive"
    headline: str
    angle: str
    summary: str
    why_reader_cares: str
    kelvin6k_connection: str
    evidence_strength: str = "High"
    novelty: str = "High"
    visual_potential: str = "High"
    image_hint: str = ""

class StrategistStrategy(BaseModel):
    topic: str
    angle: str
    content_objective: str
    target_audience: str
    recommended_format: str

class StrategistOutput(BaseModel):
    strategy: StrategistStrategy
    ideas: List[StrategistIdea] = Field(default_factory=list)
    insufficient_novel_angles: bool = False


def _build_fallback_ideas(state: RunState, topic: str) -> List[Dict[str, Any]]:
    """Dynamically construct ideas directly from content opportunities & research context."""
    opps = state.get("content_opportunities") or []
    if len(opps) >= 3:
        return [
            {
                "index": 1,
                "format": "technical_breakdown",
                "format_label": "Engineering Deep Dive",
                "headline": f"{opps[0].get('topic')[:90]}",
                "angle": f"{opps[0].get('reasoning')[:200]}",
                "summary": f"Technical breakdown of {opps[0].get('topic')[:120]}.",
                "why_reader_cares": "Directly impacts on-site structural precision and build rate.",
                "kelvin6k_connection": "Grounded in Kelvin6k robotic extrusion technology.",
                "evidence_strength": "High",
                "novelty": "High",
                "visual_potential": "High",
                "image_hint": "Detailed macro photograph of 3D-printed concrete layer striations under natural lighting.",
            },
            {
                "index": 2,
                "format": "case_study",
                "format_label": "Project Benchmark",
                "headline": f"{opps[1].get('topic')[:90]}",
                "angle": f"{opps[1].get('reasoning')[:200]}",
                "summary": f"Real-world application and deployment analysis of {opps[1].get('topic')[:120]}.",
                "why_reader_cares": "Provides empirical benchmark data for construction contractors.",
                "kelvin6k_connection": "Demonstrated across Kelvin6k deployment projects.",
                "evidence_strength": "High",
                "novelty": "Medium",
                "visual_potential": "High",
                "image_hint": "Large-format robotic 3D concrete printer operating on an active construction site.",
            },
            {
                "index": 3,
                "format": "comparison",
                "format_label": "Industry Implication",
                "headline": f"{opps[2].get('topic')[:90]}",
                "angle": f"{opps[2].get('reasoning')[:200]}",
                "summary": f"Industry-wide structural and economic implications of {opps[2].get('topic')[:120]}.",
                "why_reader_cares": "Assesses workflow integration and capital equipment efficiency.",
                "kelvin6k_connection": "Highlights Kelvin6k architectural automation advantages.",
                "evidence_strength": "High",
                "novelty": "High",
                "visual_potential": "High",
                "image_hint": "Curved structural 3D-printed concrete wall showing crisp architectural mortar finish.",
            }
        ]

    # Fallback when opportunities are not pre-populated
    return [
        {
            "index": 1,
            "format": "technical_breakdown",
            "format_label": "Engineering Deep Dive",
            "headline": f"Optimizing Extrusion Rheology in {topic[:45]}",
            "angle": f"How underlying material properties and toolpath physics impact execution in {topic}.",
            "summary": f"Exploring key engineering mechanisms governing reliable automated construction in {topic}.",
            "why_reader_cares": "Provides actionable mechanical and material parameters for structural reliability.",
            "kelvin6k_connection": "Relevant to Kelvin6k large-scale robotic printing capabilities.",
            "evidence_strength": "High",
            "novelty": "High",
            "visual_potential": "High",
            "image_hint": "Architectural photograph of a 3D-printed concrete structure showing horizontal layer striations.",
        },
        {
            "index": 2,
            "format": "case_study",
            "format_label": "Project Benchmark",
            "headline": f"Site Verification and Cycle-Time in {topic[:45]}",
            "angle": f"Evaluating on-site deployment and operational performance for {topic}.",
            "summary": f"Real-world data and site logistics for automated construction printing systems.",
            "why_reader_cares": "Demonstrates actual jobsite labor and timeline reductions.",
            "kelvin6k_connection": "Demonstrated across Kelvin6k benchmark structures.",
            "evidence_strength": "High",
            "novelty": "Medium",
            "visual_potential": "High",
            "image_hint": "Industrial robotic concrete printer operating on an active construction site.",
        },
        {
            "index": 3,
            "format": "comparison",
            "format_label": "Industry Implication",
            "headline": f"Operational Trade-offs in Modern {topic[:45]}",
            "angle": f"Assessing industry adoption hurdles and operational efficiencies surrounding {topic}.",
            "summary": f"Why construction contractors and engineers are shifting workflows toward {topic}.",
            "why_reader_cares": "Guides equipment procurement and technology adoption strategies.",
            "kelvin6k_connection": "Highlights Kelvin6k architectural automation advantages.",
            "evidence_strength": "High",
            "novelty": "High",
            "visual_potential": "High",
            "image_hint": "Modern curved 3D-printed concrete wall with visible textured mortar ridges.",
        }
    ]


def strategist_node(state: RunState) -> RunState:
    run_id = state["run_id"]
    log_id = log_agent_event(run_id, "strategist", "running",
                             input_summary=f"topic: {state.get('topic') or state.get('topic_hint')}")
    t0 = time.monotonic()
    _update_run_progress(run_id, "strategizing", "strategist")
    image_mode = state.get("image_mode") or "with_image"

    try:
        profile = get_brand_profile(state.get("brand_id") or "default") or {}
        brand_context = format_brand_context(profile, focus_topic=state.get("topic_hint"), for_agent="strategist")

        # Context components — pass ALL opportunities, not just top 1
        opps = state.get("content_opportunities") or []
        all_opps_str = ""
        if opps:
            opp_lines = []
            for i, opp in enumerate(opps[:3]):
                opp_lines.append(
                    f"OPPORTUNITY {i+1} (Score: {opp.get('overall_score')}/10 | Relevance: {opp.get('relevance')} | Novelty: {opp.get('novelty')}):\n"
                    f"  Topic: {opp.get('topic')}\n"
                    f"  Reasoning: {opp.get('reasoning')}\n"
                )
            all_opps_str = "\n".join(opp_lines)
        else:
            all_opps_str = "No validated opportunities found — use research context and topic hint."

        rep_warning = state.get("repetition_warning") or ""
        portfolio = state.get("content_portfolio") or {}
        portfolio_str = f"Recent portfolio coverage: {portfolio.get('products_distribution', {})} products, {portfolio.get('tech_distribution', {})} tech"

        # Query recent idea headlines for de-duplication
        recent_idea_headlines = _get_recent_idea_headlines(limit=10)
        recent_headlines_str = "\n".join(recent_idea_headlines) if recent_idea_headlines else "None recorded yet."
        logger.info(f"[strategist_node] Run {run_id}: Loaded {len(recent_idea_headlines)} recent idea headlines for de-duplication:\n{recent_headlines_str}")

        user_prompt = (
            f"=== BRAND PROFILE & CONSTRAINTS ===\n{brand_context}\n\n"
            f"=== VALIDATED CONTENT OPPORTUNITIES (3 DIFFERENT TOPICS — GENERATE 1 IDEA PER OPPORTUNITY) ===\n"
            f"{all_opps_str}\n\n"
            f"CRITICAL INSTRUCTION: Each idea MUST be based on a DIFFERENT opportunity above. "
            f"Do NOT generate 3 angles on the same topic. Idea 1 = Opportunity 1's topic, Idea 2 = Opportunity 2's topic, Idea 3 = Opportunity 3's topic.\n\n"
            f"{'REPETITION WARNING: ' + rep_warning if rep_warning else ''}\n"
            f"{portfolio_str}\n\n"
            f"=== RECENT IDEA HEADLINES (LAST 10 DRAFTS - DO NOT DUPLICATE) ===\n{recent_headlines_str}\n\n"
            f"=== REAL RESEARCH EVIDENCE ===\n{(state.get('research_context') or 'No research available.')[:2500]}\n\n"
            f"=== VERIFIED BRAND KNOWLEDGE ===\n{(state.get('knowledge_context') or 'No brand knowledge available.')[:1500]}\n\n"
            f"=== USER INPUT ===\n"
            f"Topic hint: {state.get('topic_hint') or '(none)'}\n"
            f"User topic: {state.get('user_topic') or '(none)'}\n"
            f"Image Mode: {image_mode}\n\n"
            "Produce the strategy, 3 ideas (one per opportunity — each on a DIFFERENT topic), and insufficient_novel_angles flag in structured JSON now."
        )

        output_data: Optional[StrategistOutput] = None

        # Attempt 1: Groq Structured Output (Fast, robust schema validation)
        try:
            groq_llm = GroqLLM()
            output_data = groq_llm.structured(
                system_prompt=STRATEGIST_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                schema=StrategistOutput,
                temperature=0.5
            )
        except Exception as groq_err:
            logger.warning(f"[strategist_node] Groq structured call failed: {groq_err}")

        # Attempt 2: Gemini Failover with max_tokens=4096
        if not output_data:
            try:
                gemini_llm = GeminiLLM()
                raw = gemini_llm.chat(
                    system_prompt=STRATEGIST_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    temperature=0.5,
                    max_tokens=4096
                )
                raw_clean = re.sub(r"```json\s*|\s*```", "", raw).strip()
                parsed = json.loads(raw_clean)
                output_data = StrategistOutput(**parsed)
            except Exception as gem_err:
                logger.warning(f"[strategist_node] Gemini chat fallback failed: {gem_err}")

        if output_data and output_data.ideas and len(output_data.ideas) >= 1:
            strategy_data = output_data.strategy.model_dump()
            ideas_raw = [i.model_dump() for i in output_data.ideas]
            insufficient_novel_angles = output_data.insufficient_novel_angles
        else:
            strategy_data = {}
            ideas_raw = []
            insufficient_novel_angles = False

        topic = strategy_data.get("topic") or state.get("topic_hint") or "Robotic 3D concrete printing"
        angle = strategy_data.get("angle") or "Engineering precision in automated construction"
        objective = strategy_data.get("content_objective") or "Technical authority"
        audience = strategy_data.get("target_audience") or "Structural engineers, builders, and roboticists"
        rec_format = strategy_data.get("recommended_format") or "technical_breakdown"

        strategy = (
            f"Topic: {topic}\n"
            f"Angle: {angle}\n"
            f"Objective: {objective}\n"
            f"Audience: {audience}\n"
            f"Format: {rec_format}"
        )

        # Normalize ideas
        ideas = []
        if isinstance(ideas_raw, list) and len(ideas_raw) >= 1:
            for i in range(min(3, len(ideas_raw))):
                src = ideas_raw[i] if i < len(ideas_raw) else {}
                format_v = (src.get("format") or "").strip().lower().replace(" ", "_") or "technical_breakdown"
                img_hint = (src.get("image_hint") or "").strip()

                if image_mode == "text_only":
                    img_hint = ""
                elif image_mode == "mix" and i == 2:
                    if all((ideas_raw[j] if j < len(ideas_raw) else {}).get("image_hint") for j in range(len(ideas_raw))):
                        img_hint = ""

                ideas.append({
                    "index": i + 1,
                    "format": format_v[:40],
                    "format_label": (src.get("format_label") or format_v).strip()[:80],
                    "angle": (src.get("angle") or "").strip()[:250],
                    "headline": (src.get("headline") or f"Idea {i+1}").strip()[:120],
                    "summary": (src.get("summary") or "").strip()[:200],
                    "why_reader_cares": (src.get("why_reader_cares") or "").strip()[:200],
                    "kelvin6k_connection": (src.get("kelvin6k_connection") or "").strip()[:200],
                    "evidence_strength": src.get("evidence_strength") or "High",
                    "novelty": src.get("novelty") or "High",
                    "visual_potential": src.get("visual_potential") or "High",
                    "image_hint": img_hint[:350],
                })
        else:
            logger.warning(f"[strategist_node] [FALLBACK ACTIVE] Building dynamic ideas from validated research opportunities.")
            ideas = _build_fallback_ideas(state, topic)

        latency = int((time.monotonic() - t0) * 1000)
        log_agent_event(run_id, "strategist", "complete",
                        output_summary=f"Strategy+{len(ideas)} distinct angles ready. Topic: '{topic[:40]}'",
                        latency_ms=latency,
                        log_id=log_id)

        return {
            **state,
            "topic": topic,
            "angle": angle,
            "strategy": strategy,
            "content_objective": objective,
            "target_audience": audience,
            "prefetched_ideas": ideas,
            "insufficient_novel_angles": insufficient_novel_angles,
            "status": "writing",
        }



    except Exception as e:
        logger.error(f"[strategist_node] Failed for run {run_id}: {e}")
        log_agent_event(run_id, "strategist", "error", error=str(e), log_id=log_id)
        fallback_topic = state.get("topic_hint") or "3D Concrete Printing Innovation"
        return {
            **state,
            "topic": fallback_topic,
            "angle": "Engineering precision and material optimization",
            "strategy": f"Topic: {fallback_topic}\nAngle: Technical authority in robotic construction.",
            "content_objective": "Technical authority",
            "target_audience": "Engineers and builders",
            "prefetched_ideas": _build_fallback_ideas(state, fallback_topic),
            "insufficient_novel_angles": False,
            "errors": state.get("errors", []) + [f"strategist: {e}"]
        }
