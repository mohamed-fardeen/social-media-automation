"""
Compatibility webhook endpoints and Telegram bot receiver.
"""
import json
import threading
import requests
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, BackgroundTasks, Request, HTTPException

from app.schemas.api import StandardResponse, IngestRequest, RunCreateRequest, ApprovalActionRequest, IdeaSelectionRequest
from app.database.supabase_client import get_supabase_client
from app.config.logging import logger
from app.services.brand_profile import get_brand_profile
from app.services.telegram_bot import send_message, delete_message, telegram_api_url

router = APIRouter()


def _parse_callback_data(data: str) -> dict:
    """Best-effort JSON parse. Telegram's compact tokens (i:…, d:…) are not JSON,
    so we just return an empty dict for them and let the prefix resolver handle
    routing."""
    try:
        return json.loads(data) if data and data.startswith("{") else {}
    except Exception:
        return {}


def _resolve_run_id_by_prefix(supa, prefix: str):
    """Look up a run_id by its 8-char hex prefix. Uses cast(id as text) so the
    ilike works on UUID columns (Postgres rejects ilike directly on uuid)."""
    if not supa or not prefix:
        return None
    try:
        res = supa.rpc("match_run_prefix", {"prefix": prefix}).execute()
        if res.data:
            return res.data[0]["id"]
    except Exception:
        pass
    # Fallback: in-memory scan of recent runs. Tolerates up to a few hundred rows.
    try:
        res = supa.table("post_runs").select("id").order(
            "created_at", desc=True
        ).limit(500).execute()
        for row in (res.data or []):
            if str(row.get("id", "")).replace("-", "").startswith(prefix):
                return row["id"]
    except Exception as e:
        logger.warning(f"run_id prefix scan failed: {e}")
    return None


def _resolve_draft_by_prefix(supa, prefix: str):
    """Returns (draft_id, run_id) for a given 8-char hex prefix of the draft id."""
    if not supa or not prefix:
        return None
    try:
        res = supa.table("post_drafts").select("id,run_id").order(
            "created_at", desc=True
        ).limit(500).execute()
        for row in (res.data or []):
            if str(row.get("id", "")).replace("-", "").startswith(prefix):
                return row["id"], row.get("run_id")
    except Exception as e:
        logger.warning(f"draft_id prefix scan failed: {e}")
    return None


@router.post("/kelvin6k/ingest")
async def webhook_ingest(payload: IngestRequest, background_tasks: BackgroundTasks):
    from app.api.v1.ingest import ingest_document
    return await ingest_document(payload, background_tasks)


@router.post("/kelvin6k/run-now")
async def webhook_run_now(payload: RunCreateRequest, background_tasks: BackgroundTasks):
    from app.api.v1.runs import create_run
    return await create_run(payload, background_tasks)


@router.post("/kelvin6k/approval-action")
async def webhook_approval_action(payload: ApprovalActionRequest):
    draft_id = payload.draft_id
    supa = get_supabase_client()
    run_id = None

    if draft_id and supa:
        try:
            res = supa.table("post_drafts").select("run_id").eq("id", draft_id).single().execute()
            if res.data:
                run_id = res.data["run_id"]
        except Exception as e:
            logger.warning(f"Could not find run_id for draft {draft_id}: {e}")

    if not run_id:
        logger.warning(f"No run found for draft {draft_id}. Approval action lost.")
        return {"ok": True}

    from app.api.v1.runs import approval_action
    return await approval_action(run_id, payload)


@router.post("/telegram/{secret}")
async def telegram_webhook(secret: str, request: Request):
    payload = await request.json()
    return await process_telegram_update(payload, secret=secret)


async def process_telegram_update(payload: dict, secret: str | None = None):
    supa = get_supabase_client()
    if not supa:
        raise HTTPException(status_code=503, detail="Database unavailable")

    profile = get_brand_profile() or {}

    expected_secret = profile.get("telegram_webhook_secret") or "default"
    if secret is not None and secret != expected_secret:
        raise HTTPException(status_code=403, detail="Invalid secret")

    bot_token = profile.get("telegram_bot_token") or ""
    chat_id = str(profile.get("telegram_chat_id") or "")

    if "callback_query" in payload:
        data = payload["callback_query"].get("data") or "{}"
        parsed = _parse_callback_data(data)
        # Compact tokens (i:… / d:…) take precedence over any JSON payload
        # because Telegram's 64-byte callback_data cap forces us to use them.
        action = parsed.get("action")
        draft_id = parsed.get("draft_id")
        run_id = parsed.get("run_id")
        choice = parsed.get("choice")

        # Compact token format: "i:{run_prefix}:{choice}" or
        # "d:{run_prefix}:{draft_prefix}:{action}" or
        # "s:{chat_suffix}:{source}" or
        # "m:{chat_suffix}:{image_mode}". Resolve to full UUIDs / chat_id by
        # matching the prefix against the DB.
        if isinstance(data, str) and any(data.startswith(p) for p in ("i:", "d:", "s:", "m:")):
            parts = data.split(":")
            action = None
            draft_id = None
            run_id = None
            choice = None
            try:
                # ── s: source-selection callback (start of /draft conversation)
                if parts[0] == "s" and len(parts) >= 3:
                    chat_suffix = parts[1]
                    source_kind = parts[2]
                    # Delete the prior "where should I draw from?" message.
                    _delete_prior(chat_id, bot_token)
                    if source_kind == "research":
                        _pending_state[chat_id] = {
                            "state": "awaiting_image_mode",
                            "source": "research",
                            "msg_ids": [],
                        }
                        if bot_token:
                            mid = send_message(
                                bot_token, chat_id,
                                "Loading recent research.\n\nNow: text-only, with image, or mix?",
                                reply_markup={
                                    "inline_keyboard": [[
                                        {"text": "Text only",
                                         "callback_data": f"m:{chat_suffix}:text_only"},
                                        {"text": "With image",
                                         "callback_data": f"m:{chat_suffix}:with_image"},
                                        {"text": "Mix",
                                         "callback_data": f"m:{chat_suffix}:mix"},
                                    ]]
                                },
                            )
                            _remember_msg(chat_id, mid)
                    elif source_kind == "user_topic":
                        _pending_state[chat_id] = {"state": "awaiting_user_topic", "msg_ids": []}
                        if bot_token:
                            mid = send_message(
                                bot_token, chat_id,
                                "What should the post be about? Type a topic in one sentence.",
                            )
                            _remember_msg(chat_id, mid)
                    return {"ok": True}

                # ── m: image-mode selection → kick off the run
                if parts[0] == "m" and len(parts) >= 3:
                    image_mode = parts[2]
                    pending = _pending_state.get(chat_id) or {}
                    # Delete the prior "loading research" or "now pick a mode" message.
                    _delete_prior(chat_id, bot_token)
                    pending["image_mode"] = image_mode
                    pending["msg_ids"] = []
                    _pending_state[chat_id] = pending
                    await _kickoff_run(chat_id, pending, bot_token)
                    return {"ok": True}

                if parts[0] == "i" and len(parts) >= 3:
                    run_prefix = parts[1][:8]
                    choice = parts[2]
                    if supa:
                        run_id = _resolve_run_id_by_prefix(supa, run_prefix)
                    action = "select_idea"
                elif parts[0] == "d" and len(parts) >= 4:
                    run_prefix = parts[1][:8]
                    draft_prefix = parts[2][:8]
                    draft_action = parts[3]
                    if supa:
                        # Try draft prefix first (more specific).
                        resolved = _resolve_draft_by_prefix(supa, draft_prefix)
                        if resolved:
                            draft_id, run_id = resolved
                        else:
                            run_id = _resolve_run_id_by_prefix(supa, run_prefix)
                    action = draft_action
            except Exception as e:
                logger.warning(f"Compact-token resolve failed: {e}")

        # Acknowledge the tap so Telegram stops showing the spinner.
        callback_id = payload["callback_query"].get("id")
        if callback_id and bot_token:
            try:
                requests.post(
                    telegram_api_url(bot_token, "answerCallbackQuery"),
                    data={"callback_query_id": callback_id, "text": "Got it"},
                    timeout=5,
                )
            except Exception:
                pass

        # Idea-selection callback (action == "select_idea").
        if action == "select_idea" and run_id and choice:
            # Delete the prior idea-selection card so the chat doesn't pile up.
            _delete_prior(chat_id, bot_token)
            _pending_state.pop(chat_id, None)
            from app.api.v1.runs import idea_action
            return await idea_action(run_id, IdeaSelectionRequest(choice=choice, decided_by="telegram"))

        if run_id and action in {"approve", "regenerate", "dismiss", "reject"} and supa:
            # If only run_id resolved, find the most recent draft for that run.
            if not draft_id:
                try:
                    res = supa.table("post_drafts").select("id").eq("run_id", run_id).order(
                        "created_at", desc=True
                    ).limit(1).execute()
                    if res.data:
                        draft_id = res.data[0]["id"]
                except Exception as e:
                    logger.warning(f"Could not find latest draft for run {run_id}: {e}")

            if action == "regenerate":
                # Regenerate is a conversation: ask the user what to change
                # and wait for their next text message.
                _pending_state[chat_id] = {
                    "state": "awaiting_regenerate_feedback",
                    "run_id": run_id,
                    "draft_id": draft_id,
                    "msg_ids": [],
                }
                if bot_token:
                    mid = send_message(
                        bot_token, chat_id,
                        "What should change? Reply with the change you want — e.g. "
                        "'make the headline punchier' or 'drop the second bullet'.",
                    )
                    _remember_msg(chat_id, mid)
                return {"ok": True}

            # Approve / Dismiss — delete the draft card so the chat stays clean.
            if action in {"approve", "dismiss", "reject"}:
                _delete_prior(chat_id, bot_token)
                _pending_state.pop(chat_id, None)

            if draft_id:
                from app.api.v1.runs import approval_action
                return await approval_action(run_id, ApprovalActionRequest(
                    draft_id=draft_id, action=action, decided_by="telegram"
                ))

        return {"ok": True}

    message = payload.get("message") or {}
    text = (message.get("text") or "").strip()
    incoming_chat_id = str((message.get("chat") or {}).get("id") or chat_id)

    # If we have a pending state for this chat, the user is in the middle of a
    # conversation. Route accordingly.
    pending = _pending_state.get(incoming_chat_id)
    if pending:
        return await _handle_pending_text(
            text, incoming_chat_id, pending, bot_token,
        )

    if text.startswith("/research"):
        from app.api.v1.research import run_research
        await run_research(type("obj", (), {"topic": None, "platforms": ["instagram", "linkedin"], "country_scope": "global", "max_results": 10})())
        if bot_token and incoming_chat_id:
            send_message(bot_token, incoming_chat_id, "Research started.")
        return {"ok": True}

    if text.startswith("/run") or text.startswith("/draft"):
        from app.api.v1.runs import chat_run
        from app.schemas.api import ChatRunRequest
        # Reset any prior conversation state for this chat.
        _pending_state.pop(incoming_chat_id, None)
        _pending_state[incoming_chat_id] = {"state": "awaiting_source", "msg_ids": []}
        if bot_token and incoming_chat_id:
            mid = send_message(
                bot_token,
                incoming_chat_id,
                "Where should I draw from?\n\n[Recent research] — load the latest insights.\n"
                "[Your own idea] — I'll ask what you want to post about.",
                reply_markup={
                    "inline_keyboard": [[
                        {"text": "Recent research",
                         "callback_data": f"s:{incoming_chat_id[-6:]}:research"},
                        {"text": "Your own idea",
                         "callback_data": f"s:{incoming_chat_id[-6:]}:user_topic"},
                    ]]
                },
            )
            _remember_msg(incoming_chat_id, mid)
        return {"ok": True}

    if text.startswith("/upload"):
        if bot_token and incoming_chat_id:
            send_message(bot_token, incoming_chat_id, "Upload happens in the app for now.")
        return {"ok": True}

    return {"ok": True}


def _parse_callback_data(data: str) -> dict:
    if data.startswith("i:"):
        parts = data.split(":", 2)
        if len(parts) == 3:
            _, choice, run_id = parts
            return {"action": "select_idea", "choice": choice, "run_id": run_id}

    if data.startswith("a:"):
        parts = data.split(":", 2)
        if len(parts) == 3:
            _, action, draft_id = parts
            return {"action": action, "draft_id": draft_id}

    try:
        return json.loads(data)
    except Exception:
        return {}


# ─── Conversational draft state machine ──────────────────────────────────────

# Per-chat conversation state for /draft. Process-local; cleared when the
# conversation ends or the run is created.
_pending_state: dict = {}  # chat_id (str) -> {"state": str, ..., "msg_ids": [int]}


def _remember_msg(chat_id: str, msg_id: Optional[int]):
    """Append a message_id to the chat's conversation history so we can
    delete it when the conversation moves on."""
    if not msg_id:
        return
    pending = _pending_state.get(chat_id) or {}
    pending.setdefault("msg_ids", []).append(int(msg_id))
    _pending_state[chat_id] = pending


def _delete_prior(chat_id: str, bot_token: str):
    """Delete every message_id the bot sent earlier in this conversation.
    Called when the user makes a new selection so the chat doesn't accumulate
    question → answer → question → answer chains."""
    pending = _pending_state.get(chat_id) or {}
    ids = pending.get("msg_ids") or []
    for mid in ids:
        try:
            delete_message(bot_token, chat_id, mid)
        except Exception as e:
            logger.warning(f"delete_message failed for chat {chat_id} msg {mid}: {e}")
    pending["msg_ids"] = []

# Source-selection callback prefix: "s:{chat_suffix}:research" or "...:user_topic"
# The chat suffix (last 6 chars of chat_id) keeps the payload under 64 bytes.


async def _handle_pending_text(text: str, chat_id: str, pending: dict, bot_token: str):
    """Step a chat through the /draft conversation based on text input."""
    state = pending.get("state")
    if state == "awaiting_user_topic":
        # User typed their topic. Move to image_mode.
        # Delete earlier bot messages (source question) so the chat stays clean.
        _delete_prior(chat_id, bot_token)
        _pending_state[chat_id] = {
            "state": "awaiting_image_mode",
            "source": "user_topic",
            "user_topic": text[:500],
            "msg_ids": [],
        }
        if bot_token:
            mid = send_message(
                bot_token, chat_id,
                "Got it. Now: text-only, with image, or one of each?\n\n"
                "[Text only] — caption only, no image generation.\n"
                "[With image] — every idea gets a generated image.\n"
                "[Mix] — at least one text-only + one with image.",
                reply_markup={
                    "inline_keyboard": [[
                        {"text": "Text only",
                         "callback_data": f"m:{chat_id[-6:]}:text_only"},
                        {"text": "With image",
                         "callback_data": f"m:{chat_id[-6:]}:with_image"},
                        {"text": "Mix",
                         "callback_data": f"m:{chat_id[-6:]}:mix"},
                    ]]
                },
            )
            _remember_msg(chat_id, mid)
        return {"ok": True}

    if state == "awaiting_regenerate_feedback":
        # User typed feedback for a Regenerate request.
        run_id = pending.get("run_id")
        draft_id = pending.get("draft_id")
        # Delete the "What should change?" prompt + the prior draft message.
        _delete_prior(chat_id, bot_token)
        _pending_state.pop(chat_id, None)
        if not run_id:
            if bot_token:
                send_message(bot_token, chat_id, "Couldn't find the run to regenerate.")
            return {"ok": True}
        # Record feedback + call the regenerate endpoint.
        from app.database.supabase_client import get_supabase_client
        supa = get_supabase_client()
        if supa:
            try:
                supa.table("agent_logs").insert({
                    "run_id": run_id,
                    "agent": "user_feedback",
                    "status": "received",
                    "input_summary": f"Regenerate: {text[:200]}",
                    "output_summary": "→ copywriter regeneration",
                    "metadata": {"raw_text": text, "draft_id": draft_id, "decided_by": "telegram"},
                }).execute()
            except Exception as e:
                logger.warning(f"Failed to record user_feedback: {e}")

        def _resume():
            try:
                from app.graph.workflow import resume_run
                resume_run(run_id, action="regenerate", feedback=text)
            except Exception as e:
                logger.error(f"Telegram regenerate failed for run {run_id}: {e}")

        threading.Thread(target=_resume, daemon=True).start()
        if bot_token:
            send_message(bot_token, chat_id, "Regenerating…")
        return {"ok": True}

    # Unknown / stale state — clear it.
    _pending_state.pop(chat_id, None)
    return {"ok": True}


async def _kickoff_run(chat_id: str, pending: dict, bot_token: str):
    """Start a draft run from the accumulated /draft conversation."""
    source = pending.get("source", "research")
    user_topic = pending.get("user_topic")
    image_mode = pending.get("image_mode", "with_image")

    from app.api.v1.runs import chat_run
    from app.schemas.api import ChatRunRequest
    payload = ChatRunRequest(
        source=source,
        user_topic=user_topic,
        image_mode=image_mode,
        platforms=["linkedin"],
        trigger="telegram",
    )

    # chat_run returns a StandardResponse with run_id; we just want it.
    result = await chat_run(payload, BackgroundTasks())
    run_id = (result.data or {}).get("run_id") if result else None
    if not run_id:
        if bot_token:
            send_message(bot_token, chat_id, "Failed to start the run.")
        return

    _pending_state[chat_id] = {
        "state": "awaiting_idea_selection",
        "run_id": run_id,
    }
    if bot_token:
        send_message(
            bot_token, chat_id,
            f"Generating 3 ideas…\n\nSource: {source}\n"
            f"{'Topic: ' + user_topic if user_topic else ''}\nMode: {image_mode}",
        )
