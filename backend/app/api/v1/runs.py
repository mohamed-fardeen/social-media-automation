"""
Runs API — create runs, get run details, handle approvals, return drafts and logs.
"""
import uuid
import threading
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.schemas.api import RunCreateRequest, ApprovalActionRequest, IdeaSelectionRequest, StandardResponse, ChatRunRequest, RegenerateFeedbackRequest
from app.database.supabase_client import get_supabase_client
from app.config.logging import logger

router = APIRouter()


def _start_run_background(run_id: str, topic_hint: Optional[str],
                           platforms: list, brand_id: Optional[str], mode: str = "full_pipeline",
                           image_mode: Optional[str] = None,
                           source_mode: Optional[str] = None,
                           user_topic: Optional[str] = None,
                           trigger: str = "manual",
                           country_scope: Optional[str] = "global"):
    """Run LangGraph workflow in background thread."""
    try:
        from app.graph.workflow import start_run
        start_run(
            run_id,
            topic_hint=topic_hint,
            platforms=platforms,
            brand_id=brand_id,
            mode=mode,
            image_mode=image_mode,
            source_mode=source_mode,
            user_topic=user_topic,
            trigger=trigger,
            country_scope=country_scope,
        )
    except Exception as e:
        logger.error(f"Background run {run_id} failed: {e}")
        supa = get_supabase_client()
        if supa:
            try:
                supa.table("post_runs").update({"status": "failed"}).eq("id", run_id).execute()
            except Exception:
                pass


@router.post("", response_model=StandardResponse)
async def create_run(payload: RunCreateRequest, background_tasks: BackgroundTasks):
    """Create and start a new content generation run."""
    run_id = str(uuid.uuid4())
    supa = get_supabase_client()
    now = datetime.now(timezone.utc).isoformat()
    mode = payload.mode or "full_pipeline"
    topic_hint = payload.topic or payload.user_topic or payload.notes

    if supa:
        base_payload = {
            "id": run_id,
            "started_at": now,
            "status": "queued",
            "trigger": payload.trigger or "manual",
            "draft_ids": [],
            "topic_hint": topic_hint,
            "created_at": now
        }
        full_payload = {
            **base_payload,
            "image_mode": payload.image_mode or "with_image",
            "source_mode": payload.source_mode or "research",
            "user_topic": payload.user_topic,
        }
        try:
            supa.table("post_runs").insert(full_payload).execute()
        except Exception as e:
            logger.warning(f"[create_run] 007 columns not yet applied: {e}")
            try:
                supa.table("post_runs").insert(base_payload).execute()
            except Exception as e2:
                logger.error(f"[create_run] insert failed: {e2}")

    # Launch in background thread so the endpoint returns immediately
    thread = threading.Thread(
        target=_start_run_background,
        args=(run_id, topic_hint,
              payload.platforms or ["instagram", "linkedin"],
              payload.brand_id,
              mode,
              payload.image_mode or "with_image",
              payload.source_mode or "research",
              payload.user_topic,
              payload.trigger or "manual",
              payload.country_scope or "global"),
        daemon=True
    )
    thread.start()

    return StandardResponse(ok=True, data={"run_id": run_id, "mode": mode})


@router.post("/draft", response_model=StandardResponse)
async def create_draft_run(payload: RunCreateRequest, background_tasks: BackgroundTasks):
    """
    Generate a draft using EXISTING research stored in Supabase.
    Does NOT trigger Apify / Firecrawl / Tavily — always uses draft_only mode.
    Use this endpoint when the user clicks 'Generate Draft' or 'Regenerate'.
    """
    run_id = str(uuid.uuid4())
    supa = get_supabase_client()
    now = datetime.now(timezone.utc).isoformat()

    if supa:
        try:
            supa.table("post_runs").insert({
                "id": run_id,
                "started_at": now,
                "status": "queued",
                "trigger": "manual",
                "draft_ids": [],
                "topic_hint": payload.topic or payload.notes,
                "created_at": now
            }).execute()
        except Exception as e:
            logger.error(f"Failed to create draft run row: {e}")

    thread = threading.Thread(
        target=_start_run_background,
        args=(run_id, payload.topic or payload.notes,
              payload.platforms or ["instagram", "linkedin"],
              payload.brand_id,
              "draft_only"),   # ← always draft_only, no scraping
        daemon=True
    )
    thread.start()

    return StandardResponse(ok=True, data={"run_id": run_id, "mode": "draft_only"})


@router.get("/{run_id}", response_model=StandardResponse)
async def get_run(run_id: str):
    supa = get_supabase_client()
    if not supa:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        res = supa.table("post_runs").select("*").eq("id", run_id).single().execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Run not found")
        return StandardResponse(ok=True, data=res.data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{run_id}/drafts", response_model=StandardResponse)
async def get_run_drafts(run_id: str):
    supa = get_supabase_client()
    if not supa:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        res = supa.table("post_drafts") \
            .select("*") \
            .eq("run_id", run_id) \
            .order("created_at", desc=True) \
            .execute()
        return StandardResponse(ok=True, data={"drafts": res.data or []})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{run_id}/drafts/{draft_id}", response_model=StandardResponse)
async def delete_run_draft(run_id: str, draft_id: str):
    supa = get_supabase_client()
    if not supa:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        res = supa.table("post_drafts").delete().eq("id", draft_id).eq("run_id", run_id).execute()
        
        # Also clean up from the run's draft_ids array
        run_res = supa.table("post_runs").select("draft_ids").eq("id", run_id).execute()
        if run_res.data and len(run_res.data) > 0:
            current_drafts = run_res.data[0].get("draft_ids") or []
            if draft_id in current_drafts:
                current_drafts.remove(draft_id)
                supa.table("post_runs").update({"draft_ids": current_drafts}).eq("id", run_id).execute()

        return StandardResponse(ok=True, data={"message": "Draft deleted successfully", "deleted_id": draft_id})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{run_id}/logs", response_model=StandardResponse)
async def get_run_logs(run_id: str):
    supa = get_supabase_client()
    if not supa:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        res = supa.table("agent_logs") \
            .select("*") \
            .eq("run_id", run_id) \
            .order("started_at") \
            .execute()
        return StandardResponse(ok=True, data={"logs": res.data or []})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{run_id}/approval", response_model=StandardResponse)
async def approval_action(run_id: str, payload: ApprovalActionRequest):
    """
    Handle human approval actions: approve, regenerate, reject.
    Resumes the paused LangGraph workflow accordingly.
    """
    action = "reject" if payload.action == "dismiss" else payload.action
    supa = get_supabase_client()

    # Mark draft status in DB immediately
    draft_id = payload.draft_id
    if supa and draft_id:
        status_map = {
            "approve": "approved",
            "reject": "rejected",
            "regenerate": "draft",
            "dismiss": "rejected"
        }
        try:
            supa.table("post_drafts").update({
                "status": status_map.get(action, "draft")
            }).eq("id", draft_id).execute()
        except Exception as e:
            logger.warning(f"Could not update draft status: {e}")

    if action == "reject":
        if supa:
            try:
                supa.table("post_runs").update({
                    "status": "rejected",
                    "finished_at": datetime.now(timezone.utc).isoformat()
                }).eq("id", run_id).execute()
            except Exception:
                pass
        return StandardResponse(ok=True, data={"message": "Run rejected."})

    # Resume LangGraph workflow in background thread
    def _resume():
        try:
            from app.graph.workflow import resume_run
            resume_run(run_id, action=action, feedback=payload.feedback)
        except Exception as e:
            logger.error(f"Resume failed for run {run_id}: {e}")

    thread = threading.Thread(target=_resume, daemon=True)
    thread.start()

    return StandardResponse(ok=True, data={
        "run_id": run_id,
        "action": action,
        "message": f"Action '{action}' received. Workflow resuming."
    })


@router.post("/{run_id}/idea-action", response_model=StandardResponse)
async def idea_action(run_id: str, payload: IdeaSelectionRequest):
    """
    Handle the user's pick from the Telegram idea-selection card.

    - "1" / "2" / "3"  → resume the graph for that single idea.
    - "all"           → fan out 3 parallel generations via asyncio.gather.
    - "dismiss"       → mark run rejected, ack.
    """
    choice = payload.choice
    supa = get_supabase_client()

    indices: list[int] = []
    if choice in ("1", "2", "3"):
        indices = [int(choice)]
    elif choice == "all":
        indices = [1, 2, 3]
    elif choice == "dismiss":
        indices = []
    elif isinstance(choice, str):
        # Support comma-separated choices like "1,2", "1,3", "2,3", "1,2,3"
        indices = [int(x.strip()) for x in choice.split(",") if x.strip().isdigit() and int(x.strip()) in (1, 2, 3)]

    if choice == "dismiss":
        if supa:
            try:
                supa.table("post_runs").update({
                    "status": "rejected",
                    "idea_status": "dismissed",
                    "selected_idea_indices": [],
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", run_id).execute()
            except Exception as e:
                logger.warning(f"Failed to mark run dismissed: {e}")
        # Acknowledge in Telegram so the message doesn't dangle.
        try:
            from app.services.brand_profile import get_brand_profile
            from app.services.telegram_bot import send_message
            prof = get_brand_profile("default") or {}
            tok = prof.get("telegram_bot_token")
            chat = prof.get("telegram_chat_id")
            if tok and chat:
                send_message(tok, chat, f"Run {run_id[:8]} dismissed — no drafts generated.")
        except Exception:
            pass
        return StandardResponse(ok=True, data={"run_id": run_id, "action": "dismiss"})

    # Persist the selection immediately so the web UI reflects the choice.
    if supa:
        try:
            supa.table("post_runs").update({
                "selected_idea_indices": indices,
                "idea_status": "generating" if choice == "all" else "selected",
                "status": "generating_drafts",
            }).eq("id", run_id).execute()
        except Exception as e:
            logger.warning(f"Failed to persist idea selection: {e}")

    def _run_one(idx: int):
        from app.graph.workflow import resume_run
        try:
            resume_run(run_id, action=f"idea:{idx}", idea_index=idx)
        except Exception as e:
            logger.error(f"resume_run failed for run {run_id} idea {idx}: {e}")

    if len(indices) == 1:
        # Single-idea path: the existing per-idea Telegram approval message
        # fires from save_draft_node → send_approval_notification. Nothing to
        # do here besides launching the resume.
        threading.Thread(target=_run_one, args=(indices[0],), daemon=True).start()
    else:
        # "All three" path: parallel per-idea resumes; once the last one
        # finishes assembling drafts, send one consolidated batch message.
        from app.services.telegram_bot import send_draft_batch
        from app.services.brand_profile import get_brand_profile
        import time as _time

        remaining = [i for i in indices]
        lock = threading.Lock()

        def _run_one_and_maybe_batch(idx: int):
            done = False
            try:
                _run_one(idx)
            finally:
                with lock:
                    if idx in remaining:
                        remaining.remove(idx)
                    done = not remaining
            if done:
                # Give Supabase a moment to settle the latest inserts.
                _time.sleep(3)
                try:
                    # Read the run's trigger — only telegram-triggered runs
                    # send a batch message to the bot.
                    run_row = supa.table("post_runs").select("trigger").eq(
                        "id", run_id
                    ).limit(1).execute()
                    trigger = ((run_row.data or [{}])[0].get("trigger") or "").lower()
                    if trigger == "telegram":
                        prof = get_brand_profile("default") or {}
                        tok = prof.get("telegram_bot_token")
                        chat = prof.get("telegram_chat_id")
                        if tok and chat and supa:
                            res = supa.table("post_drafts").select(
                                "id,platform,format,format_label,idea_index,image_url,caption"
                            ).eq("run_id", run_id).execute()
                            drafts = res.data or []
                            if drafts:
                                send_draft_batch(tok, chat, run_id, drafts)
                except Exception as e:
                    logger.error(f"send_draft_batch failed for run {run_id}: {e}")

        for idx in indices:
            threading.Thread(target=_run_one_and_maybe_batch, args=(idx,), daemon=True).start()

    return StandardResponse(ok=True, data={
        "run_id": run_id,
        "action": choice,
        "selected_idea_indices": indices,
        "message": f"Generating draft(s) for idea(s) {indices}.",
    })


@router.post("/chat", response_model=StandardResponse)
async def chat_run(payload: ChatRunRequest, background_tasks: BackgroundTasks):
    """Web modal entry point. Accepts source (research vs user_topic) and
    image_mode (text_only / with_image / mix), threads them through the graph,
    and returns the new run_id."""
    run_id = str(uuid.uuid4())
    supa = get_supabase_client()
    now = datetime.now(timezone.utc).isoformat()
    topic_hint = payload.user_topic if payload.source == "user_topic" else None

    if supa:
        # Insert with full payload first; fall back without the 007 columns
        # if the migration hasn't been applied.
        base_payload = {
            "id": run_id,
            "started_at": now,
            "status": "queued",
            "trigger": payload.trigger or "web_modal",
            "draft_ids": [],
            "topic_hint": topic_hint,
            "created_at": now,
        }
        full_payload = {
            **base_payload,
            "image_mode": payload.image_mode,
            "source_mode": payload.source,
            "user_topic": payload.user_topic,
        }
        try:
            supa.table("post_runs").insert(full_payload).execute()
        except Exception as e:
            logger.warning(f"[chat_run] 007 columns not yet applied: {e}")
            try:
                supa.table("post_runs").insert(base_payload).execute()
            except Exception as e2:
                logger.error(f"[chat_run] insert failed: {e2}")

    thread = threading.Thread(
        target=_start_run_background,
        args=(run_id, topic_hint,
              payload.platforms or ["linkedin"],
              payload.brand_id,
              payload.mode or "draft_only",
              payload.image_mode,
              payload.source,
              payload.user_topic,
              payload.trigger or "web_modal",
              payload.country_scope or "global"),
        daemon=True,
    )
    thread.start()

    return StandardResponse(ok=True, data={
        "run_id": run_id,
        "source": payload.source,
        "image_mode": payload.image_mode,
        "user_topic": payload.user_topic,
    })


@router.post("/{run_id}/regenerate-feedback", response_model=StandardResponse)
async def regenerate_with_feedback(run_id: str, payload: RegenerateFeedbackRequest):
    """Web-style regenerate: store the feedback as an agent_log entry, then
    resume the workflow with action='regenerate' + feedback. Returns immediately
    after dispatching the background thread."""
    supa = get_supabase_client()
    feedback = payload.feedback.strip()

    # Record the feedback as an agent_log event for the timeline.
    if supa:
        try:
            supa.table("agent_logs").insert({
                "run_id": run_id,
                "agent": "user_feedback",
                "status": "received",
                "input_summary": f"Regenerate: {feedback[:200]}",
                "output_summary": "→ copywriter regeneration",
                "metadata": {"raw_text": feedback, "decided_by": "web_modal"},
            }).execute()
        except Exception as e:
            logger.warning(f"Failed to record user feedback: {e}")

    def _resume():
        try:
            from app.graph.workflow import resume_run
            resume_run(run_id, action="regenerate", feedback=feedback)
        except Exception as e:
            logger.error(f"Regenerate failed for run {run_id}: {e}")

    threading.Thread(target=_resume, daemon=True).start()

    return StandardResponse(ok=True, data={
        "run_id": run_id,
        "action": "regenerate",
        "feedback": feedback,
        "message": "Regeneration in progress.",
    })
