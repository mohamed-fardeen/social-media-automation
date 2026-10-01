"""
Content Intelligence Agent / Node.
Evaluates research evidence and brand knowledge against Content Memory and Portfolio,
filtering out generic or repetitive topics and scoring high-value candidate opportunities.
"""
import time
from typing import Dict, Any, List
from app.graph.state import RunState
from app.agents.log_helper import log_agent_event
from app.services.content_intelligence.memory import retrieve_content_memory, check_topic_repetition
from app.services.content_intelligence.portfolio import get_content_portfolio
from app.services.content_intelligence.evaluator import evaluate_content_opportunities
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


def content_intelligence_node(state: RunState) -> RunState:
    run_id = state["run_id"]
    log_id = log_agent_event(
        run_id, "content_intelligence", "running",
        input_summary=f"Evaluating opportunities for topic: {state.get('topic') or state.get('topic_hint')}"
    )
    t0 = time.monotonic()
    _update_run_progress(run_id, "strategizing", "content_intelligence")

    candidate_topic = (
        state.get("user_topic")
        or state.get("topic_hint")
        or state.get("topic")
        or "Robotic 3D concrete printing"
    )

    try:
        # 1. Retrieve Content Memory
        memory_items = retrieve_content_memory(candidate_topic, brand_id=state.get("brand_id") or "default")

        # 2. Check for Topic Repetition
        is_repetitive, max_sim, rep_reasons = check_topic_repetition(
            candidate_topic=candidate_topic,
            candidate_angle=state.get("angle") or "",
            memory_items=memory_items,
            similarity_threshold=0.82
        )
        rep_warning = "; ".join(rep_reasons) if is_repetitive else None
        if rep_warning:
            logger.warning(f"[ContentIntelligence] Repetition detected for run {run_id}: {rep_warning}")

        # 3. Retrieve Portfolio Distribution
        portfolio_summary = get_content_portfolio(brand_id=state.get("brand_id") or "default")

        # 4. Evaluate Content Opportunities
        opportunities = evaluate_content_opportunities(
            research_context=state.get("research_context") or "",
            knowledge_context=state.get("knowledge_context") or "",
            topic_hint=candidate_topic,
            memory_items=memory_items,
            portfolio_summary=portfolio_summary,
            max_candidates=3
        )

        # Convert to serializable dicts for state and persistence
        opps_dicts = [opp.model_dump() for opp in opportunities]
        memory_dicts = [item.model_dump() for item in memory_items[:6]]
        portfolio_dict = portfolio_summary.model_dump()

        accepted_count = sum(1 for o in opportunities if o.decision in ("ACCEPT", "NARROW"))
        top_score = opportunities[0].overall_score if opportunities else 0.0

        latency = int((time.monotonic() - t0) * 1000)
        log_agent_event(
            run_id, "content_intelligence", "complete",
            output_summary=f"{len(opportunities)} opportunities scored (top: {top_score}/10, {accepted_count} accepted)",
            latency_ms=latency,
            log_id=log_id
        )

        return {
            **state,
            "content_opportunities": opps_dicts,
            "content_memory": memory_dicts,
            "content_portfolio": portfolio_dict,
            "repetition_warning": rep_warning,
            "status": "strategizing"
        }

    except Exception as e:
        logger.error(f"[ContentIntelligence] Node failed for run {run_id}: {e}")
        log_agent_event(run_id, "content_intelligence", "error", error=str(e), log_id=log_id)
        return {
            **state,
            "content_opportunities": [],
            "content_memory": [],
            "content_portfolio": {},
            "repetition_warning": None,
            "errors": state.get("errors", []) + [f"content_intelligence: {e}"]
        }
