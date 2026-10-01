import time
from typing import Any, Dict, List
from app.graph.state import RunState
from app.agents.log_helper import log_agent_event
from app.schemas.research_plan import ResearchPlan, SocialSearchTarget, ResearchDocument
from app.schemas.agent_outputs import ResearchOutput
from app.services.research.router import SourceRouter
from app.services.llm.groq import GroqLLM, GrokLLM
from app.services.brand_profile import format_brand_context, get_brand_profile
from app.database.supabase_client import get_supabase_client
from app.config.logging import logger

PLANNER_SYSTEM_PROMPT = """You are a strategic research planner for Kelvin6k (construction 3D printing and robotic concrete printing).
Analyze the user's topic hint and target platforms.
Determine WHAT information is required for effective content creation, focusing strictly on high-value, novel, and concrete developments in the concrete 3D-printing and robotic construction sector.

Guidelines:
1. Prioritize relevance to Kelvin6k's industry: robotic concrete construction, polar vs gantry printer setups, geopolymer/concrete materials, buildability, and competitor systems.
2. Formulate 1-3 targeted Google search queries seeking concrete engineering details, verified project names, or specific breakthroughs rather than generic, high-level statements.

Output a JSON object specifying:
1. summary_of_intent: High level goal.
2. web_queries: 1-3 targeted Google search queries for discovery.
3. target_urls: Any specific URLs mentioned or required for deep extraction (or empty list if none).
4. social_targets: List of social platform search targets if social insights are needed (platform: instagram, reddit, x, linkedin).
5. needs_deep_crawl: Boolean flag."""

SYNTHESIZER_SYSTEM_PROMPT = """You are a senior social media research analyst working for Kelvin6k (construction 3D printing).
Synthesize the provided raw research evidence into a concise, high-signal research brief.

Your goal is to identify genuinely useful, novel, and relevant developments. Do NOT treat every trend or news item as a post opportunity.
Filter out generic marketing fluff and PR noise. Only keep findings with high content potential and audience value.

Strict Guidelines:
1. PRIORITIZE NOVELTY & RELEVANCE: Distinguish meaningful industry developments (e.g. competitor progress, material breakthroughs, code compliance) from generic noise (e.g. "3D printing is growing").
2. PROVIDE WHY IT MATTERS: Explain clearly WHY a finding matters to the industry and the audience, providing enough evidence for downstream agents to understand its significance.
3. STRICT FACTUAL ACCURACY: Do NOT invent or extrapolate any statistics, numbers, dates, company names, or project details. Every signal must be traceable to the provided raw evidence.
4. RESEARCH SIGNALS ONLY: Provide strong factual signals and raw data. Do NOT attempt to write the final social post copy or define strategy.

Return structured JSON: {"trends": [...], "competitor_signals": [...], "industry_topics": [...], "summary": "..."}"""


def _update_run_progress(run_id: str, status: str, agent: str) -> None:
    """Best-effort update of post_runs.status + current_agent for frontend progress."""
    try:
        from app.database.supabase_client import get_supabase_client
        supa = get_supabase_client()
        if supa:
            supa.table("post_runs").update(
                {"status": status, "current_agent": agent}
            ).eq("id", run_id).execute()
    except Exception:
        pass  # non-fatal — never block the pipeline


def research_node(state: RunState) -> RunState:
    run_id = state["run_id"]
    topic_hint = state.get("topic_hint") or "business leadership and AI innovation"
    target_platforms = state.get("platforms") or ["instagram", "linkedin"]

    log_id = log_agent_event(run_id, "research", "running",
                             input_summary=f"topic_hint: {topic_hint} | platforms: {','.join(target_platforms)}")
    t0 = time.monotonic()

    # ── Fast-path: draft_only skips ALL external scraping and LLM planning ──
    # MUST be checked before SourceRouter() is instantiated — SourceRouter
    # tries to connect to Firecrawl on init and can block for minutes on timeout.
    if state.get("mode") == "draft_only":
        _update_run_progress(run_id, "researching", "research")
        profile = get_brand_profile(state.get("brand_id") or "default") or {}
        brand_context = format_brand_context(profile)
        industry = profile.get("industry") or topic_hint
        context, evidence_dicts = _load_saved_research_context(topic_hint)
        latency = int((time.monotonic() - t0) * 1000)
        log_agent_event(run_id, "research", "complete",
                        output_summary=f"draft_only: loaded {len(evidence_dicts)} saved insights (no scraping)",
                        latency_ms=latency,
                        log_id=log_id)
        return {
            **state,
            "research_context": context or f"Use saved brand context and topic: {topic_hint}",
            "brand_context": brand_context,
            "research_evidence": evidence_dicts,
            "topic": topic_hint if topic_hint != "business leadership and AI innovation" else industry,
            "status": "strategizing",
        }

    try:
        _update_run_progress(run_id, "researching", "research")
        llm = GrokLLM()
        router = SourceRouter(max_concurrent=5)
        profile = get_brand_profile(state.get("brand_id") or "default") or {}
        brand_context = format_brand_context(profile)
        industry = profile.get("industry") or topic_hint

        # Phase 1: Grok Research Planner (Determines WHAT information is needed)
        country_scope = (state.get("country_scope") or "global").strip().lower()
        scope_instruction = (
            "GEOGRAPHIC SCOPE: INDIA. Focus specifically on the Indian construction 3D printing ecosystem, Indian infrastructure projects, CPWD, Indian startups (e.g. Tvasta, Godrej, L&T 3DCP), and Indian regulatory codes."
            if country_scope == "india"
            else "GEOGRAPHIC SCOPE: GLOBAL. Focus on worldwide 3D concrete printing breakthroughs, global competitors (e.g. COBOD, PERI, CyBe, ICON), and international engineering standards."
        )

        planner_prompt = (
            f"Company profile:\n{brand_context}\n\n"
            f"{scope_instruction}\n\n"
            f"Topic hint: '{topic_hint}'\nTarget platforms: {', '.join(target_platforms)}"
        )
        plan: ResearchPlan = llm.structured(
            system_prompt=PLANNER_SYSTEM_PROMPT,
            user_prompt=planner_prompt,
            schema=ResearchPlan
        )

        if not plan:
            # Fallback plan if LLM planning fails
            scope_suffix = "in India" if country_scope == "india" else "worldwide"
            plan = ResearchPlan(
                summary_of_intent=f"Research on {topic_hint} ({scope_suffix}) for the configured company",
                web_queries=[
                    f"{industry} industry trends {scope_suffix} 2026",
                    f"{industry} competitor content strategy {scope_suffix}",
                    f"{topic_hint} audience signals {scope_suffix}",
                ],
                social_targets=[SocialSearchTarget(platform=p, query_or_handle=f"{topic_hint} {scope_suffix}") for p in target_platforms[:2]]
            )

        # Phase 2: Deterministic Source Router (Executes providers & deduplicates evidence)
        evidence_docs: List[ResearchDocument] = router.execute_plan(plan, max_total_docs=10)

        try:
            from datetime import datetime, timezone
            from app.api.v1.research import _build_research_rows, _list_from_profile
            
            now_iso = datetime.now(timezone.utc).isoformat()
            competitors = _list_from_profile(profile, "competitors")
            company_name = profile.get("company_name") or "the company"
            
            rows = _build_research_rows(
                evidence_docs,
                company=company_name,
                topic=topic_hint,
                industry=industry,
                competitors=competitors,
                now=now_iso,
            )
            
            if rows:
                from app.database.supabase_client import get_supabase_client
                supa = get_supabase_client()
                if supa:
                    supa.table("research_insights").insert(rows).execute()
                    logger.info(f"Persisted {len(rows)} research rows to global insights.")
        except Exception as e:
            logger.warning(f"Failed to persist research insights: {e}")

        # Convert documents to transient dictionaries for RunState with source_type
        evidence_dicts = []
        for doc in evidence_docs:
            d_dict = doc.model_dump()
            is_comp = any(c.lower() in (doc.title + " " + doc.content).lower() for c in ["cobod", "peri", "cybe", "icon", "tvasta"])
            d_dict["source_type"] = "COMPETITOR_INFORMATION" if is_comp else "INDUSTRY_RESEARCH"
            evidence_dicts.append(d_dict)

        # Phase 3: Grok Synthesizer (Generates structured research brief from evidence)
        raw_text_blocks = [
            f"[{doc.get('source_type', 'INDUSTRY_RESEARCH')}] [{doc.get('platform', 'WEB').upper()}/{doc.get('provider', '').upper()}] {doc.get('title')}\nSource: {doc.get('url')}\nContent: {doc.get('content', '')[:1000]}"
            for doc in evidence_dicts
        ]

        raw_text = "\n\n".join(raw_text_blocks) if raw_text_blocks else f"Topic: {topic_hint}"

        output: ResearchOutput = llm.structured(
            system_prompt=SYNTHESIZER_SYSTEM_PROMPT,
            user_prompt=(
                f"Company profile:\n{brand_context}\n\n"
                f"Topic: '{topic_hint}'\nIntent: '{plan.summary_of_intent}'\n\nEvidence:\n{raw_text}"
            ),
            schema=ResearchOutput
        )

        if output:
            context = (
                f"TRENDS: {'; '.join(output.trends)}\n"
                f"COMPETITOR SIGNALS: {'; '.join(output.competitor_signals)}\n"
                f"TOPICS: {'; '.join(output.industry_topics)}\n"
                f"SUMMARY: {output.summary}"
            )
            topic = output.industry_topics[0] if output.industry_topics else topic_hint
        else:
            context = f"Research summary on: {topic_hint}"
            topic = topic_hint

        latency = int((time.monotonic() - t0) * 1000)
        log_agent_event(run_id, "research", "complete",
                        output_summary=f"{len(evidence_docs)} evidence docs · {len(output.trends if output else [])} trends",
                        latency_ms=latency,
                        log_id=log_id)

        return {
            **state,
            "research_context": context,
            "brand_context": brand_context,
            "research_evidence": evidence_dicts,
            "topic": topic,
            "status": "strategizing"
        }

    except Exception as e:
        logger.error(f"Research node failed for run {run_id}: {e}")
        log_agent_event(run_id, "research", "error", error=str(e), log_id=log_id)
        return {
            **state,
            "errors": state.get("errors", []) + [f"research: {e}"],
            "research_context": f"Research on: {state.get('topic_hint', 'business')}",
            "research_evidence": [],
            "topic": state.get("topic_hint", "business insights"),
            "status": "strategizing"
        }


def _load_saved_research_context(topic_hint: str) -> tuple[str, List[Dict[str, Any]]]:
    supa = get_supabase_client()
    if not supa:
        return "", []
    try:
        res = supa.table("research_insights") \
            .select("*") \
            .order("captured_at", desc=True) \
            .limit(40) \
            .execute()
        raw_rows = res.data or []
    except Exception as e:
        logger.warning(f"Could not load saved research insights for draft-only run: {e}")
        return "", []

    if not raw_rows:
        return "", []

    # Deduplicate by URL and normalized title
    seen_titles = set()
    seen_urls = set()
    deduped_rows = []

    for r in raw_rows:
        title = (r.get("title") or "").strip()
        url = (r.get("url") or "").strip()
        norm_title = "".join(c.lower() for c in title if c.isalnum())[:40]

        if not norm_title or norm_title in seen_titles:
            continue
        if url and url in seen_urls:
            continue

        seen_titles.add(norm_title)
        if url:
            seen_urls.add(url)
        deduped_rows.append(r)

    # Diversity Selection: Select up to 6 distinct insights across source kinds
    by_kind: Dict[str, List[Dict[str, Any]]] = {}
    for r in deduped_rows:
        k = r.get("source_kind", "industry") or "industry"
        by_kind.setdefault(k, []).append(r)

    selected_rows: List[Dict[str, Any]] = []
    # Round-robin pick from kinds (trend, competitor, industry, product, etc.)
    max_to_pick = 6
    while len(selected_rows) < max_to_pick:
        picked_any = False
        for kind in list(by_kind.keys()):
            if by_kind[kind] and len(selected_rows) < max_to_pick:
                selected_rows.append(by_kind[kind].pop(0))
                picked_any = True
        if not picked_any:
            break

    if not selected_rows:
        selected_rows = deduped_rows[:max_to_pick]

    lines = [
        f"- [{'COMPETITOR_INFORMATION' if row.get('source_kind') == 'competitor' else 'INDUSTRY_RESEARCH'}] {row.get('title', '').strip()}: {row.get('summary', '').strip()[:300]}"
        for row in selected_rows
    ]
    context = "RECENT INDUSTRY RESEARCH INSIGHTS:\n" + "\n".join(lines)
    evidence = [
        {
            "id": row.get("id"),
            "title": row.get("title"),
            "url": row.get("url"),
            "content": row.get("summary"),
            "provider": row.get("source"),
            "platform": "saved_research",
            "source_type": "COMPETITOR_INFORMATION" if row.get("source_kind") == "competitor" else "INDUSTRY_RESEARCH",
            "metadata": {"source_kind": row.get("source_kind"), "topic_hint": topic_hint},
        }
        for row in selected_rows
    ]
    return context, evidence


