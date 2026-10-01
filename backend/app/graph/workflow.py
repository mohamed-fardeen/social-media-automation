"""
Main LangGraph workflow for Kelvin6k Social Engine V2.

Graph flow:
START → init_run → research → knowledge → strategist → ideation
      → await_idea_selection (interrupt; Telegram user picks 1/2/3/all/dismiss)
         │
         ├── chosen idea(s) → copywriter → visual → image_gen → save_draft
         │     → human_approval (interrupt)
         │         ├── APPROVE → publisher → END
         │         ├── REGENERATE → copywriter
         │         └── REJECT → END
         └── dismiss → END

Per-idea iteration is handled outside the graph: idea_action() calls resume_run()
once per chosen idea (parallel for "all"), each producing its own pair of
post_drafts rows tagged with idea_index.
"""
import uuid
import time
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.graph.state import RunState
from app.graph.checkpointer import save_checkpoint, load_checkpoint
from app.agents.research import research_node
from app.agents.knowledge import knowledge_node
from app.agents.content_intelligence import content_intelligence_node
from app.agents.strategist import strategist_node
from app.agents.editorial_brief import editorial_brief_node
from app.agents.copywriter import copywriter_node
from app.agents.visual import visual_node
from app.agents.qa import qa_node, content_qa_node, vision_qa_node
from app.agents.publisher import publisher_node
from app.agents.log_helper import log_agent_event
from app.services.image.generator import generate_and_store_image
from app.services.approval_notifications import send_approval_notification
from app.services.brand_profile import get_brand_profile, format_brand_context
from app.services.telegram_bot import send_idea_selection_message
from app.database.supabase_client import get_supabase_client
from app.config.logging import logger



# ─── Node: Initialize Run ────────────────────────────────────────────────────

def init_run_node(state: RunState) -> RunState:
    run_id = state["run_id"]
    logger.info(f"[Workflow] Starting run {run_id}")
    supa = get_supabase_client()

    now = datetime.now(timezone.utc).isoformat()
    if supa:
        # Build base payload; the new 007 columns (image_mode, source_mode,
        # user_topic) are best-effort so the run still initializes when the
        # migration hasn't been applied.
        base_payload = {
            "id": run_id,
            "started_at": now,
            "status": "researching",
            "trigger": state.get("trigger") or "manual",
            "draft_ids": [],
            "topic_hint": state.get("topic_hint"),
        }
        full_payload = {
            **base_payload,
            "image_mode": state.get("image_mode"),
            "source_mode": state.get("source_mode"),
            "user_topic": state.get("user_topic"),
        }
        try:
            supa.table("post_runs").upsert(full_payload).execute()
        except Exception as e:
            logger.warning(f"[init_run_node] 007 columns not yet applied, "
                           f"writing without image_mode/source_mode/user_topic: {e}")
            try:
                supa.table("post_runs").upsert(base_payload).execute()
            except Exception as e2:
                logger.error(f"[init_run_node] DB init failed: {e2}")

    return {
        **state,
        "status": "researching",
        "errors": [],
        "draft_ids": [],
        "knowledge_citations": [],
        "instagram_hashtags": [],
        "linkedin_hashtags": [],
        "version": state.get("version", 1)
    }


# ─── Node: Ideation ───────────────────────────────────────────────────────────

IDEATION_SYSTEM_PROMPT = """You are a senior social media strategist working for Kelvin6k (construction 3D printing).
You receive: the brand profile, real research insights, the brand's own knowledge context (including synthesized Kelvin6k connections), and a validated strategy/angle.

Your job is to produce THREE post ideas that are:
1. DIFFERENT APPROACHES TO THE SAME INSIGHT: The three candidates must be genuinely different angles/perspectives to communicate the SAME strategic insight defined in the input. Do not generate three generic variations or repetitive summaries.
   The differences in approaches should focus on:
   - Technical explanation (explain the specific engineering/robotic/material mechanism relevant to THIS topic)
   - Industry/Macro implication (economic impact, supply chain, design freedom, or regulatory standards)
   - Kelvin6k project/product connection (grounded in real Kelvin6k projects like MES, ZOHO, GCC, or machines like ATON, ATOM, G.MINI, ONLY when supported by brand knowledge)
   - Technical comparison (comparing competing methodologies, topologies, or operational workflows)
   - Educational angle (teaching a specific domain concept from the research)
   - Contrarian angle (challenging common misconceptions based on evidence)

2. STRICTLY FACTUAL & REALISTIC (ZERO HALLUCINATION):
   - NEVER invent or hallucinate awards, honors, or recognitions.
   - NEVER invent product features, telemetry capabilities, power sources (e.g., solar), or technical specifications unless explicitly stated in the VERIFIED BRAND KNOWLEDGE.
   - Do NOT invent or extrapolate statistics, numbers, or percentages.
   - Do NOT invent founder experiences or first-person opinions.
   - Do NOT invent customer results or project results.
   - Every claim must be strictly traceable to the provided inputs. If the information isn't there, do not include it.

3. INSIGHT-FIRST, FORMAT-SECOND: First identify the core insight approach, and then choose a fitting format (e.g., data_snack, contrarian, case_study, carousel, comparison, founder_pov, behind_the_scenes, listicle, etc.). Do not select a format first and then make up an idea to fit it.

Output format for each idea:
- index (1..3)
- format (short slug, e.g. data_snack, contrarian, case_study, carousel, comparison, founder_pov,
  behind_the_scenes, listicle, or anything descriptive you choose)
- format_label (reader-facing label, e.g. "Chart of the week", "Behind the build",
  "What we learned", "5 things to know", etc.)
- angle (exactly what the post argues or reveals, in one sentence — must cite or reference a
  real data point or finding from the research)
- headline (<= 80 chars, punchy, format-appropriate)
- summary (1 sentence: why a reader in this brand's target audience would stop scrolling)
- image_hint (concrete visual direction for an AI image generator for ONE image;
  leave empty string if this idea works better as pure text)

Return JSON: {"ideas": [{"index":1, "format":"...", ...}, ...]}

Constraints:
- Three ideas, each with a different format AND different angle.
- If image_mode is text_only: leave image_hint empty on all three.
- If image_mode is with_image: every idea must have a vivid image_hint.
- If image_mode is mix: at least one idea must have an empty image_hint.
- Never use generic placeholder headlines like "3 things to know about [topic]".
  Every headline must feel specific and tied to the actual research content.
"""



def _build_fallback_ideas(state):
    """Emergency fallback using Groq GPT-OSS to dynamically synthesize 3 ideas.
    Never relies on raw mechanical string slicing."""
    topic = (
        state.get("user_topic")
        or state.get("topic_hint")
        or state.get("topic")
        or "robotic 3D concrete printing"
    )
    research = (state.get("research_context") or "")[:1500]

    try:
        from app.services.llm.groq import GroqLLM
        import json as _json
        llm = GroqLLM()
        prompt = (
            f"Topic: {topic}\n"
            f"Research: {research}\n\n"
            "Generate 3 distinct post ideas for Kelvin6k (construction 3D printing). "
            "Return JSON: {\"ideas\": [{\"index\":1, \"format\":\"insight\", \"format_label\":\"Industry insight\", \"angle\":\"...\", \"headline\":\"...\", \"summary\":\"...\", \"image_hint\":\"...\"}, ...]}"
        )
        raw = llm.chat(
            system_prompt="You are a social media strategist for Kelvin6k. Return valid JSON only.",
            user_prompt=prompt,
            temperature=0.7,
        )
        import re
        raw_clean = re.sub(r"```json\s*|\s*```", "", raw).strip()
        parsed = _json.loads(raw_clean)
        ideas_list = parsed.get("ideas") if isinstance(parsed, dict) else parsed
        if isinstance(ideas_list, list) and len(ideas_list) >= 3:
            return [
                {
                    "index": i + 1,
                    "format": (ideas_list[i].get("format") or "insight")[:40],
                    "format_label": (ideas_list[i].get("format_label") or "Insight")[:80],
                    "angle": (ideas_list[i].get("angle") or "")[:200],
                    "headline": (ideas_list[i].get("headline") or f"Idea {i+1}")[:120],
                    "summary": (ideas_list[i].get("summary") or "")[:200],
                    "image_hint": (ideas_list[i].get("image_hint") or "")[:300],
                }
                for i in range(3)
            ]
    except Exception as e:
        logger.warning(f"[_build_fallback_ideas] Groq fallback failed: {e}")

    # Structured safety fallback with high-quality domain copy
    return [
        {
            "index": 1,
            "format": "insight",
            "format_label": "Industry insight",
            "angle": f"How {topic} is driving structural efficiency and material savings in modern construction.",
            "headline": f"The Real Impact of {topic[:40]} on Modern Builds",
            "summary": f"Why construction leaders and roboticists are rethinking build methods with {topic}.",
            "image_hint": "Architectural cross-section of a 3D-printed concrete wall showing distinct horizontal layer beads.",
        },
        {
            "index": 2,
            "format": "data_point",
            "format_label": "Data point",
            "angle": f"Key operational and speed metrics when deploying automated 3DCP for {topic}.",
            "headline": f"By the Numbers: What {topic[:35]} Delivers on Site",
            "summary": f"Analyzing print cycle speed, material deposition rates, and labor reduction.",
            "image_hint": "High-detail view of a heavy-duty industrial printhead extruding precise mortar beads.",
        },
        {
            "index": 3,
            "format": "trend_take",
            "format_label": "Trend take",
            "angle": f"Moving beyond formwork: how {topic} enables architectural freedom and localized production.",
            "headline": f"Why Formwork-Free Printing is the Future of {topic[:35]}",
            "summary": "Challenging conventional cast-in-place concrete with robotic precision.",
            "image_hint": "Curved parametric 3D-printed concrete facade showing prominent horizontal layer striations.",
        },
    ]




def ideation_node(state: RunState) -> RunState:
    """Strategist proposes 3 candidate ideas. Persists them to post_runs.ideas,
    sends the Telegram selection card, and pauses the graph at await_idea_selection.

    Fast-path: if strategist_node already produced ideas via its combined call
    (prefetched_ideas), skip the LLM call entirely.
    """
    run_id = state["run_id"]
    log_id = log_agent_event(run_id, "strategist", "running",
                             input_summary="Drafting 3 candidate ideas")
    t0 = time.monotonic()
    # Update run status so frontend shows progress
    try:
        _supa = get_supabase_client()
        if _supa:
            _supa.table("post_runs").update(
                {"status": "strategizing", "current_agent": "ideation"}
            ).eq("id", run_id).execute()
    except Exception:
        pass

    image_mode = state.get("image_mode") or "with_image"

    # Fast-path: use ideas already produced by the combined strategist call
    prefetched = state.get("prefetched_ideas")
    if isinstance(prefetched, list) and len(prefetched) == 3:
        ideas = prefetched
        logger.info(
            f"[ideation_node] Run {run_id}: using {len(ideas)} prefetched ideas "
            f"from combined strategist call -- skipping LLM round-trip."
        )
        latency = int((time.monotonic() - t0) * 1000)
        log_agent_event(run_id, "strategist", "complete",
                        output_summary=f"Used {len(ideas)} prefetched ideas (fast-path)",
                        latency_ms=latency, log_id=log_id)
    else:
        ideas = []
        try:
            import json as _json
            import re as _re

            _profile = get_brand_profile(state.get("brand_id") or "default") or {}
            brand_context = format_brand_context(_profile, focus_topic=state.get("topic_hint"), for_agent="strategist")

            user_prompt = (
                f"=== BRAND PROFILE ===\n{brand_context}\n\n"
                f"=== STRATEGY & ANGLE ===\n"
                f"Strategy: {state.get('strategy') or '(none yet)'}\n"
                f"Angle: {state.get('angle') or '(none yet)'}\n"
                f"Objective: {state.get('content_objective') or '(none yet)'}\n\n"
                f"=== REAL RESEARCH (use this as your primary idea source) ===\n"
                f"{(state.get('research_context') or 'No research available.')[:2500]}\n\n"
                f"=== BRAND KNOWLEDGE ===\n"
                f"{(state.get('knowledge_context') or 'No brand knowledge available.')[:1000]}\n\n"
                f"=== USER INPUT ===\n"
                f"Topic hint: {state.get('topic_hint') or '(none)'}\n"
                f"User-typed topic: {state.get('user_topic') or '(none — use research)'}\n\n"
                f"=== IMAGE MODE ===\n"
                f"{image_mode}: "
                f"{'leave image_hint EMPTY on all three ideas.' if image_mode == 'text_only' else ''}"
                f"{'every idea MUST have a vivid, concrete image_hint.' if image_mode == 'with_image' else ''}"
                f"{'at least ONE idea must have image_hint empty; others may have one.' if image_mode == 'mix' else ''}"
                f"\n\nNow produce 3 post ideas grounded in the research above, "
                f"fitting this brand's voice and audience."
            )

            raw = None
            try:
                from app.services.llm.groq import GroqLLM
                raw = GroqLLM().chat(
                    system_prompt=IDEATION_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    temperature=0.7,
                    max_tokens=4096,
                )
            except Exception as g_err:
                logger.warning(f"[ideation_node] Groq call failed ({g_err}). Failing over to GeminiLLM...")
                from app.services.llm.gemini import GeminiLLM
                raw = GeminiLLM().chat(
                    system_prompt=IDEATION_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    temperature=0.7,
                    max_tokens=4096,
                )

            try:
                raw_clean = _re.sub(r"```json\s*|\s*```", "", raw).strip()
                parsed = _json.loads(raw_clean)
                ideas = parsed.get("ideas") if isinstance(parsed, dict) else parsed
            except Exception:
                ideas = []

            if not isinstance(ideas, list) or len(ideas) < 3:
                opps = state.get("content_opportunities") or []
                if len(opps) >= 3:
                    ideas = [
                        {
                            "index": 1,
                            "format": "technical_breakdown",
                            "format_label": "Engineering Deep Dive",
                            "headline": f"{opps[0].get('topic')[:90]}",
                            "angle": f"{opps[0].get('reasoning')[:250]}",
                            "summary": f"Technical breakdown of {opps[0].get('topic')[:120]}.",
                            "image_hint": "Detailed macro photograph of 3D-printed concrete layer striations.",
                        },
                        {
                            "index": 2,
                            "format": "case_study",
                            "format_label": "Project Benchmark",
                            "headline": f"{opps[1].get('topic')[:90]}",
                            "angle": f"{opps[1].get('reasoning')[:250]}",
                            "summary": f"Real-world deployment benchmark of {opps[1].get('topic')[:120]}.",
                            "image_hint": "Industrial robotic concrete printer operating on an active construction site.",
                        },
                        {
                            "index": 3,
                            "format": "comparison",
                            "format_label": "Industry Implication",
                            "headline": f"{opps[2].get('topic')[:90]}",
                            "angle": f"{opps[2].get('reasoning')[:250]}",
                            "summary": f"Industry analysis of {opps[2].get('topic')[:120]}.",
                            "image_hint": "Curved structural 3D-printed concrete wall showing architectural texture.",
                        }
                    ]
                else:
                    ideas = _build_fallback_ideas(state)
            else:
                normalized = []
                for i in range(3):
                    src = ideas[i] if i < len(ideas) else {}
                    format_v = (src.get("format") or "").strip().lower().replace(" ", "_") or "technical_breakdown"
                    normalized.append({
                        "index": i + 1,
                        "format": format_v[:40],
                        "format_label": (src.get("format_label") or src.get("format") or format_v).strip()[:80],
                        "angle": (src.get("angle") or "").strip()[:500],
                        "headline": (src.get("headline") or src.get("angle") or f"Idea {i+1}").strip()[:120],
                        "summary": (src.get("summary") or "").strip()[:280],
                        "image_hint": (src.get("image_hint") or "").strip()[:300],
                    })
                ideas = normalized
                if image_mode == "text_only":
                    for idea in ideas:
                        idea["image_hint"] = ""
                elif image_mode == "mix":
                    if all(idea.get("image_hint") for idea in ideas):
                        ideas[-1]["image_hint"] = ""
        except Exception as e:
            logger.error(f"[ideation_node] failed: {e}")
            ideas = _build_fallback_ideas(state)

        latency = int((time.monotonic() - t0) * 1000)
        log_agent_event(run_id, "strategist", "complete",
                        output_summary=f"Proposed {len(ideas)} ideas",
                        latency_ms=latency, log_id=log_id)


    # ── Log the generated ideas so we can see them in the server logs ──
    logger.info(f"[ideation_node] Run {run_id}: {len(ideas)} ideas generated.")
    for idea in ideas:
        logger.info(
            f"  Idea {idea.get('index')}: [{idea.get('format_label')}] "
            f"{idea.get('headline')[:60] if idea.get('headline') else '(no headline)'}  "
            f"image_hint={'YES' if idea.get('image_hint') else 'EMPTY'}"
        )

    # Persist to DB and send Telegram.
    supa = get_supabase_client()
    profile = get_brand_profile(state.get("brand_id") or "default") or {}
    bot_token = profile.get("telegram_bot_token")
    chat_id = profile.get("telegram_chat_id")

    logger.info(
        f"[ideation_node] Run {run_id}: "
        f"trigger='{(state.get('trigger') or '').strip().lower()}' "
        f"bot_token={'SET' if bot_token else 'MISSING'} "
        f"chat_id={'SET' if chat_id else 'MISSING'}"
    )

    if supa:
        base_payload = {
            "status": "awaiting_idea_selection",
            "current_agent": "strategist",
        }
        full_payload = {
            **base_payload,
            "ideas": ideas,
            "idea_status": "proposed",
        }
        try:
            supa.table("post_runs").update(full_payload).eq("id", run_id).execute()
            logger.info(f"[ideation_node] DB updated with ideas + idea_status=proposed.")
        except Exception as e:
            logger.warning(f"[ideation_node] 005 columns not yet applied, writing without ideas/idea_status: {e}")
            try:
                supa.table("post_runs").update(base_payload).eq("id", run_id).execute()
                logger.info(f"[ideation_node] DB updated with base_payload only.")
            except Exception as e2:
                logger.error(f"[ideation_node] DB update failed: {e2}")
    else:
        logger.warning(f"[ideation_node] No Supabase client — ideas NOT written to DB.")

    trigger = (state.get("trigger") or "").strip().lower()
    if bot_token and chat_id and trigger == "telegram":
        logger.info(
            f"[ideation_node] Sending idea-selection card to Telegram "
            f"(chat_id={chat_id}, run={run_id[:8]})…"
        )
        try:
            ok = send_idea_selection_message(bot_token, chat_id, run_id, ideas)
            logger.info(
                f"[ideation_node] send_idea_selection_message → {'OK' if ok else 'FAILED (returned False)'}"
            )
        except Exception as e:
            logger.error(f"[ideation_node] Telegram send RAISED: {e}")
    else:
        logger.warning(
            f"[ideation_node] Telegram NOT sent. "
            f"trigger='{trigger}' "
            f"bot_token={'SET' if bot_token else 'MISSING'} "
            f"chat_id={'SET' if chat_id else 'MISSING'} "
            f"(need trigger=='telegram' and both tokens set)"
        )

    return {
        **state,
        "ideas": ideas,
        "selected_idea_indices": [],
        "status": "awaiting_idea_selection",
        "current_agent": "strategist",
    }


def await_idea_selection_node(state: RunState) -> RunState:
    """Pause point — graph suspends here until the idea selection callback arrives
    via /runs/{run_id}/idea-action which then calls resume_run()."""
    trigger = state.get("trigger") or "web_modal"
    logger.info(f"[Workflow] Run {state['run_id']} awaiting idea selection (trigger='{trigger}').")
    try:
        save_checkpoint(state["run_id"], {**state, "status": "awaiting_idea_selection"})
    except Exception as e:
        logger.warning(f"await_idea_selection checkpoint save failed: {e}")
    return state



# ─── Node: Image Generation ───────────────────────────────────────────────────

def image_gen_node(state: RunState) -> RunState:
    run_id = state["run_id"]
    log_id = log_agent_event(run_id, "visual", "running",
                             input_summary="Generating hero image")
    t0 = time.monotonic()

    # Skip conditions (image_mode / image_hint):
    # - text_only: user opted out of images entirely
    # - empty image_hint + mix: this particular idea was chosen to be text-only
    image_mode = state.get("image_mode") or "with_image"
    image_hint = (state.get("image_hint") or "").strip()
    visual_prompt = (state.get("visual_prompt") or "").strip()
    skip = image_mode == "text_only" or (image_mode == "mix" and not image_hint)

    logger.info(
        f"[image_gen_node] Run {run_id}: "
        f"image_mode='{image_mode}' "
        f"image_hint={'SET' if image_hint else 'EMPTY'} "
        f"visual_prompt={'SET' if visual_prompt else 'EMPTY'} "
        f"skip={skip}"
    )

    if skip:
        latency = int((time.monotonic() - t0) * 1000)
        log_agent_event(run_id, "visual", "complete",
                        output_summary="Image skipped (text-only mode)",
                        latency_ms=latency, log_id=log_id)
        logger.info(f"[image_gen_node] Run {run_id}: Skipped — returning image_url=None.")
        return {**state, "image_url": None, "status": "writing"}

    prompt_to_use = visual_prompt or image_hint or "Professional business photography"
    referenced_product = state.get("referenced_product")
    visual_spec = state.get("visual_spec") or {}
    requires_overlay = visual_spec.get("requires_post_label_overlay", False)
    overlay_spec = visual_spec.get("label_overlay_spec") if requires_overlay else None

    logger.info(f"[image_gen_node] Run {run_id}: Generating image (ref_product={referenced_product}, overlay={'YES' if overlay_spec else 'NO'}) with prompt: {prompt_to_use[:120]}")
    image_url, image_provider_used = asyncio.run(generate_and_store_image(
        prompt_to_use,
        run_id,
        referenced_product=referenced_product,
        label_overlay_spec=overlay_spec
    ))
    logger.info(f"[image_gen_node] Run {run_id}: image_url → {image_url or 'NONE (generation failed)'} (Provider: {image_provider_used or 'NONE'})")

    latency = int((time.monotonic() - t0) * 1000)
    log_agent_event(run_id, "visual", "complete",
                    output_summary=f"Hero image rendered via {image_provider_used}" if image_url else "Image skipped (no provider)",
                    latency_ms=latency,
                    log_id=log_id)

    return {
        **state,
        "image_url": image_url,
        "image_provider_used": image_provider_used,
    }


# ─── Node: Save Draft ─────────────────────────────────────────────────────────

def save_draft_node(state: RunState) -> RunState:
    run_id = state["run_id"]
    supa = get_supabase_client()
    now = datetime.now(timezone.utc).isoformat()
    version = state.get("version", 1)
    draft_ids = []

    li_id = str(uuid.uuid4())

    idea_index = state.get("current_idea_index")
    format_v = state.get("format")
    format_label = state.get("format_label")
    image_hint = state.get("image_hint")
    image_provider = state.get("image_provider_used")
    qa_status = state.get("qa_status") or ("verified_pass" if state.get("qa_passed", True) else "flagged")
    degraded_steps = state.get("degraded_steps") or []

    logger.info(
        f"[save_draft_node] Run {run_id}: "
        f"idea_index={idea_index} format='{format_v}' format_label='{format_label}' "
        f"image_url={'SET' if state.get('image_url') else 'NONE'} provider={image_provider} "
        f"qa_status='{qa_status}' degraded_steps={degraded_steps} "
        f"linkedin_draft_len={len(state.get('linkedin_draft') or '')}"
    )

    # LinkedIn-only. The product scope is now LinkedIn (Instagram was dropped).
    editorial_brief = state.get("editorial_brief")
    visual_spec = state.get("visual_spec")
    qa_results = {
        "content_qa": state.get("content_qa"),
        "visual_qa": state.get("visual_qa"),
        "qa_passed": state.get("qa_passed", True),
        "qa_status": qa_status,
        "qa_issues": state.get("qa_issues", [])
    }
    claim_evidence = state.get("claim_evidence")

    li_draft = {
        "id": li_id,
        "run_id": run_id,
        "platform": "linkedin",
        "version": version,
        "caption": state.get("linkedin_draft", ""),
        "hashtags": state.get("linkedin_hashtags", []),
        "image_url": state.get("image_url"),
        "image_prompt": state.get("visual_prompt"),
        "strategy": state.get("strategy"),
        "reasoning": state.get("angle"),
        "status": "pending_approval",
        "idea_index": idea_index,
        "format": format_v,
        "format_label": format_label,
        "image_hint": image_hint,
        "editorial_brief": editorial_brief,
        "visual_spec": visual_spec,
        "qa_results": qa_results,
        "claim_evidence": claim_evidence,
        "visual_type": (visual_spec or {}).get("visual_type") or (editorial_brief or {}).get("visual_type"),
        "created_at": now,
        "metrics": {
            "image_provider_used": image_provider,
            "qa_status": qa_status,
            "degraded_steps": degraded_steps
        }
    }

    if supa:
        try:
            supa.table("post_drafts").insert([li_draft]).execute()
            logger.info(f"[save_draft_node] Draft {li_id[:8]} inserted into post_drafts (Provider: {image_provider}, QA: {qa_status}).")
            # Append rather than overwrite so "all three" accumulates 3 draft IDs.
            existing = supa.table("post_runs").select("draft_ids").eq("id", run_id).single().execute()
            prior = (existing.data or {}).get("draft_ids") or []
            supa.table("post_runs").update({
                "status": "awaiting_approval",
                "draft_ids": list(dict.fromkeys(prior + [li_id])),
                "editorial_brief": editorial_brief,
                "content_opportunities": state.get("content_opportunities"),
                "qa_results": qa_results,
                "repetition_warning": state.get("repetition_warning"),
                "notes": f"degraded_steps={json.dumps(degraded_steps)}" if degraded_steps else None
            }).eq("id", run_id).execute()
            logger.info(f"[save_draft_node] post_runs updated → awaiting_approval.")
        except Exception as e:
            logger.error(f"[save_draft_node] Failed to save draft with extended fields: {e}")
            try:
                # Fallback insertion without extended 009 columns if not yet migrated
                clean_li = {k: v for k, v in li_draft.items() if k not in ("editorial_brief", "visual_spec", "qa_results", "claim_evidence", "visual_type")}
                supa.table("post_drafts").insert([clean_li]).execute()
                supa.table("post_runs").update({
                    "status": "awaiting_approval",
                    "draft_ids": list(dict.fromkeys(prior + [li_id]))
                }).eq("id", run_id).execute()
            except Exception as e2:
                logger.error(f"[save_draft_node] Fallback insert also failed: {e2}")

    else:
        logger.warning(f"[save_draft_node] No Supabase client — draft NOT saved.")
        logger.info(f"[LocalStore] LinkedIn draft created: li={li_id[:8]}")

    profile = get_brand_profile(state.get("brand_id") or "default") or {}
    approval_channel = (profile.get("approval_channel") or "none").strip().lower()
    telegram_bot_token = profile.get("telegram_bot_token")
    telegram_chat_id = profile.get("telegram_chat_id")
    selected_indices = state.get("selected_idea_indices") or []
    is_batch_run = len(selected_indices) > 1
    trigger = (state.get("trigger") or "").strip().lower()
    is_telegram_run = trigger == "telegram"

    logger.info(
        f"[save_draft_node] Approval guard: "
        f"channel='{approval_channel}' "
        f"bot_token={'SET' if telegram_bot_token else 'MISSING'} "
        f"chat_id={'SET' if telegram_chat_id else 'MISSING'} "
        f"is_batch={is_batch_run} "
        f"trigger='{trigger}' is_telegram={is_telegram_run}"
    )

    for draft in (li_draft,):
        if (approval_channel == "telegram" and telegram_bot_token and telegram_chat_id
                and not is_batch_run and is_telegram_run):
            logger.info(f"[save_draft_node] Sending approval notification to Telegram…")
            try:
                send_approval_notification(
                    bot_token=telegram_bot_token,
                    chat_id=telegram_chat_id,
                    draft=draft,
                    run_id=run_id,
                )
                logger.info(f"[save_draft_node] Approval notification sent for draft {li_id[:8]}.")
            except Exception as e:
                logger.warning(f"[save_draft_node] Approval notification failed for {draft['id']}: {e}")
        else:
            logger.info(
                f"[save_draft_node] Approval notification SKIPPED "
                f"(channel='{approval_channel}' is_batch={is_batch_run} is_telegram={is_telegram_run})"
            )

    draft_ids = [li_id]

    # Save checkpoint so run can be resumed on approval
    save_checkpoint(run_id, {**state, "draft_ids": draft_ids, "status": "awaiting_approval"})
    logger.info(f"[save_draft_node] Checkpoint saved. Run {run_id[:8]} now awaiting_approval.")

    return {
        **state,
        "draft_ids": draft_ids,
        "status": "awaiting_approval"
    }


# ─── Node: Human Approval Interrupt ──────────────────────────────────────────
#
# LangGraph interrupts execution here; the workflow resumes when
# POST /api/v1/runs/{run_id}/approval is called.

def human_approval_node(state: RunState) -> RunState:
    """Pause point — workflow suspends until approval action is received."""
    logger.info(f"[Workflow] Run {state['run_id']} awaiting human approval.")
    return state


# ─── Routing ──────────────────────────────────────────────────────────────────

def approval_router(state: RunState) -> str:
    """Routes based on approval action stored in state."""
    action = state.get("notes", "")  # We re-use 'notes' to carry action temporarily

    if "approve" in action:
        return "publisher"
    elif "regenerate" in action:
        return "editorial_brief"
    else:
        return END


# ─── Graph Construction ───────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(RunState)

    graph.add_node("init_run", init_run_node)
    graph.add_node("research", research_node)
    graph.add_node("knowledge", knowledge_node)
    graph.add_node("content_intelligence", content_intelligence_node)
    graph.add_node("strategist", strategist_node)
    graph.add_node("ideation", ideation_node)
    graph.add_node("await_idea_selection", await_idea_selection_node)
    graph.add_node("editorial_brief", editorial_brief_node)
    graph.add_node("copywriter", copywriter_node)
    graph.add_node("content_qa", content_qa_node)   # ← NEW: text QA before image
    graph.add_node("visual", visual_node)
    graph.add_node("image_gen", image_gen_node)
    graph.add_node("vision_qa", vision_qa_node)     # ← NEW: image QA after image
    graph.add_node("qa", qa_node)                   # legacy, kept for compatibility
    graph.add_node("save_draft", save_draft_node)
    graph.add_node("human_approval", human_approval_node)
    graph.add_node("publisher", publisher_node)

    graph.set_entry_point("init_run")
    graph.add_edge("init_run", "research")
    graph.add_edge("research", "knowledge")
    graph.add_edge("knowledge", "content_intelligence")
    graph.add_edge("content_intelligence", "strategist")
    graph.add_edge("strategist", "ideation")
    graph.add_edge("ideation", "await_idea_selection")
    graph.add_edge("await_idea_selection", "editorial_brief")
    graph.add_edge("editorial_brief", "copywriter")
    # ── Content QA BEFORE image gen ──────────────────────────────────────────
    graph.add_edge("copywriter", "content_qa")
    graph.add_conditional_edges(
        "content_qa",
        lambda s: "visual" if s.get("qa_passed", True) else ("copywriter" if s.get("version", 1) <= 3 else "save_draft"),
        {
            "visual": "visual",
            "copywriter": "copywriter",   # auto-retry loop
            "save_draft": "save_draft",   # give up after 3 tries (skip image)
        }
    )
    # ── Image generation + Vision QA ─────────────────────────────────────────
    graph.add_edge("visual", "image_gen")
    graph.add_edge("image_gen", "vision_qa")
    graph.add_edge("vision_qa", "save_draft")
    graph.add_edge("save_draft", "human_approval")

    # Conditional routing from approval
    graph.add_conditional_edges(
        "human_approval",
        approval_router,
        {
            "publisher": "publisher",
            "editorial_brief": "editorial_brief",
            END: END
        }
    )
    graph.add_edge("publisher", END)

    return graph



# Build graph singleton
_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph().compile(checkpointer=MemorySaver())
    return _graph


# ─── Public API ──────────────────────────────────────────────────────────────

def start_run(run_id: str, topic_hint: Optional[str] = None,
              platforms: list = None, brand_id: Optional[str] = None,
              mode: str = "full_pipeline",
              image_mode: Optional[str] = None,
              source_mode: Optional[str] = None,
              user_topic: Optional[str] = None,
              trigger: str = "manual",
              country_scope: Optional[str] = "global") -> Dict[str, Any]:
    """Start a new LangGraph workflow run."""
    # Ensure trigger is always a non-empty string so every downstream guard
    # (trigger == "telegram") is reliable. Default to "web_modal" for web runs.
    trigger = (trigger or "web_modal").strip().lower()

    initial_state: RunState = {
        "run_id": run_id,
        "brand_id": brand_id,
        "platforms": platforms or ["instagram", "linkedin"],
        "mode": mode,
        "topic_hint": topic_hint,
        "topic": None,
        "angle": None,
        "research_context": None,
        "research_evidence": None,
        "knowledge_context": None,
        "knowledge_citations": [],
        "content_opportunities": None,
        "content_memory": None,
        "content_portfolio": None,
        "repetition_warning": None,
        "strategy": None,
        "content_objective": None,
        "target_audience": None,
        "prefetched_ideas": None,
        "editorial_brief": None,
        "claim_evidence": None,
        "instagram_draft": None,
        "instagram_hashtags": [],
        "linkedin_draft": None,
        "linkedin_hashtags": [],
        "cta": None,
        "visual_spec": None,
        "visual_prompt": None,
        "image_url": None,
        "referenced_product": None,
        "content_qa": None,
        "visual_qa": None,
        "qa_passed": None,
        "qa_issues": [],
        "status": "queued",
        "feedback": None,
        "version": 1,
        "draft_ids": [],
        "errors": [],
        "notes": None,
        "ideas": None,
        "selected_idea_indices": [],
        "current_idea_index": None,
        "format": None,
        "format_label": None,
        "image_hint": None,
        "image_mode": image_mode,
        "source_mode": source_mode,
        "user_topic": user_topic,
        "country_scope": country_scope or "global",
        "trigger": trigger,
    }


    graph = get_graph()
    config = {"configurable": {"thread_id": run_id}}
    last_state = initial_state

    try:
        for chunk in graph.stream(initial_state, config=config,
                                  stream_mode="values",
                                  interrupt_before=["await_idea_selection"]):
            # Stream runs until idea-selection interrupt.
            last_state = chunk

        # ── Persist state to DB checkpoint immediately after the interrupt ──
        # The graph stops BEFORE await_idea_selection_node runs, so that node's
        # own save_checkpoint() never executes. We save here so that resume_run()
        # can always restore full state (including ideas) even after a server
        # restart that wipes the in-memory MemorySaver.
        try:
            save_checkpoint(run_id, {**last_state, "status": "awaiting_idea_selection"})
            logger.info(f"[start_run] Checkpoint saved for run {run_id} at idea-selection pause.")
        except Exception as ck_err:
            logger.warning(f"[start_run] Checkpoint save failed (non-fatal): {ck_err}")

        return last_state
    except Exception as e:
        logger.error(f"Graph stream failed for run {run_id}: {e}")
        return {**initial_state, "status": "failed", "errors": [str(e)]}


def resume_run(run_id: str, action: str, feedback: Optional[str] = None,
               idea_index: Optional[int] = None) -> Dict[str, Any]:
    """Resume a paused workflow. Three pause points:

    - await_idea_selection: pass action='idea:{1|2|3}' plus idea_index.
      Threads the chosen idea's angle into topic_hint so the copywriter/visual
      agents develop *that* idea (not the strategist's original single angle).
    - human_approval: pass action='approve' | 'regenerate' | 'dismiss'.
    """
    graph = get_graph()
    config = {"configurable": {"thread_id": run_id}}

    # ── Restore state: in-memory MemorySaver first, DB checkpoint as fallback ──
    # After a server restart the MemorySaver is empty. We merge DB state into
    # the graph's thread so update_state / invoke don't operate on a blank slate.
    try:
        current_state = graph.get_state(config).values or {}
    except Exception as e:
        logger.warning(f"[resume_run] Could not read graph state for {run_id}: {e}")
        current_state = {}

    db_state: dict = {}
    try:
        db_state = load_checkpoint(run_id) or {}
    except Exception as e:
        logger.warning(f"[resume_run] load_checkpoint failed for {run_id}: {e}")

    current = {**db_state, **current_state}

    # We inject the restored DB state at the "await_idea_selection" interrupt
    # point using as_node so LangGraph places the checkpoint correctly in its
    # internal history — no agents re-execute.
    if not current_state and db_state:
        logger.info(f"[resume_run] MemorySaver empty for {run_id}; re-seeding from DB checkpoint.")
        try:
            seed_state = {
                **db_state,
                "run_id": run_id,
                "status": "awaiting_idea_selection",
                "notes": None,
            }
            # Inject at await_idea_selection position — no agents re-execute.
            graph.update_state(config, seed_state, as_node="await_idea_selection")
            logger.info(f"[resume_run] MemorySaver re-seeded for run {run_id}.")
            # Refresh current after re-seeding.
            try:
                current_state = graph.get_state(config).values or {}
                current = {**db_state, **current_state}
            except Exception:
                pass
        except Exception as seed_err:
            logger.warning(f"[resume_run] Re-seed failed (will try update_state anyway): {seed_err}")

    if action.startswith("idea:") and idea_index is not None:
        # If we don't have ideas in state, fall back to reading post_runs.ideas
        ideas = current.get("ideas") or []
        if not ideas:
            try:
                from app.database.supabase_client import get_supabase_client
                s = get_supabase_client()
                if s:
                    res = s.table("post_runs").select("ideas").eq("id", run_id).single().execute()
                    ideas = (res.data or {}).get("ideas") or []
            except Exception:
                ideas = []

        chosen = next((i for i in ideas if i.get("index") == idea_index), None)
        angle = (chosen or {}).get("angle") or current.get("angle") or ""
        headline = (chosen or {}).get("headline") or ""
        summary = (chosen or {}).get("summary") or ""
        new_topic_hint = (
            f"{headline}\n\nAngle: {angle}\nWhy: {summary}".strip()
            if headline or summary
            else (current.get("topic_hint") or "")
        )
        try:
            graph.update_state(config, {
                "topic_hint": new_topic_hint,
                "angle": angle or current.get("angle"),
                "current_idea_index": idea_index,
                "format": (chosen or {}).get("format"),
                "format_label": (chosen or {}).get("format_label"),
                "image_hint": (chosen or {}).get("image_hint"),
                "notes": action,
                "feedback": feedback,
                "editorial_brief": None,
                "claim_evidence": None,
                "instagram_draft": None,
                "instagram_hashtags": [],
                "linkedin_draft": None,
                "linkedin_hashtags": [],
                "visual_spec": None,
                "visual_prompt": None,
                "image_url": None,
                "content_qa": None,
                "visual_qa": None,
                "qa_passed": None,
                "qa_issues": [],
                # Carry forward the trigger so save_draft_node's Telegram guard
                # keeps working after a re-seed.
                "trigger": current.get("trigger") or "web_modal",
            })

        except Exception as e:
            logger.error(f"[resume_run] idea update_state failed: {e}")
    else:
        try:
            graph.update_state(
                config,
                {"notes": action, "feedback": feedback, "version": None}
            )
        except Exception as e:
            logger.warning(f"[resume_run] update_state failed for {run_id}: {e}")

    # Bump version for regeneration
    if action == "regenerate":
        new_version = current.get("version", 1) + 1
        try:
            graph.update_state(config, {"version": new_version})
        except Exception:
            pass

    try:
        interrupt_before = ["human_approval"] if action.startswith("idea:") else (
            ["human_approval"] if action == "regenerate" else []
        )
        result = graph.invoke(None, config=config, interrupt_before=interrupt_before)
        return result
    except Exception as e:
        logger.error(f"[resume_run] Graph invoke failed for run {run_id}: {e}")
        return {"run_id": run_id, "status": "failed", "errors": [str(e)]}
