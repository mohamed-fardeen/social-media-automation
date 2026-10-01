from __future__ import annotations

import asyncio
import json
import threading
from typing import Any, Dict, Optional

import requests

from app.config.logging import logger

TELEGRAM_API_BASE = "https://api.telegram.org/bot"
_poller_lock = threading.Lock()
_poller_stop: Optional[threading.Event] = None
_poller_thread: Optional[threading.Thread] = None
_poller_token: Optional[str] = None


def telegram_api_url(bot_token: str, method: str) -> str:
    return f"{TELEGRAM_API_BASE}{bot_token}/{method}"


def verify_bot_token(bot_token: Optional[str]) -> bool:
    if not bot_token:
        return False
    try:
        res = requests.get(telegram_api_url(bot_token, "getMe"), timeout=10)
        ok = bool(res.ok and res.json().get("ok"))
        if not ok:
            logger.warning(f"Telegram getMe failed: {res.status_code} {res.text}")
        return ok
    except Exception as e:
        logger.warning(f"Telegram token verification failed: {e}")
        return False


def set_bot_commands(bot_token: str) -> bool:
    commands = [
        {"command": "research", "description": "Run research only"},
        {"command": "upload", "description": "Upload a source or asset"},
        {"command": "draft", "description": "Generate a new draft"},
        {"command": "run", "description": "Run the full workflow"},
    ]
    try:
        res = requests.post(
            telegram_api_url(bot_token, "setMyCommands"),
            data={"commands": json.dumps(commands)},
            timeout=10,
        )
        ok = bool(res.ok and res.json().get("ok"))
        if not ok:
            logger.warning(f"Telegram setMyCommands failed: {res.status_code} {res.text}")
        return ok
    except Exception as e:
        logger.warning(f"Telegram commands setup failed: {e}")
        return False


def set_webhook(bot_token: str, webhook_url: str, secret_token: Optional[str] = None) -> bool:
    payload: Dict[str, Any] = {"url": webhook_url}
    if secret_token:
        payload["secret_token"] = secret_token
    try:
        res = requests.post(telegram_api_url(bot_token, "setWebhook"), data=payload, timeout=10)
        ok = bool(res.ok and res.json().get("ok"))
        if not ok:
            logger.warning(f"Telegram setWebhook failed: {res.status_code} {res.text}")
        return ok
    except Exception as e:
        logger.warning(f"Telegram webhook setup failed: {e}")
        return False


def delete_webhook(bot_token: str) -> bool:
    try:
        res = requests.post(telegram_api_url(bot_token, "deleteWebhook"), timeout=10)
        ok = bool(res.ok and res.json().get("ok"))
        if not ok:
            logger.warning(f"Telegram deleteWebhook failed: {res.status_code} {res.text}")
        return ok
    except Exception as e:
        logger.warning(f"Telegram webhook delete failed: {e}")
        return False


def start_local_polling(bot_token: Optional[str]) -> bool:
    """Start a dev-only Telegram getUpdates loop when no public webhook is configured."""
    global _poller_stop, _poller_thread, _poller_token

    if not bot_token:
        return False

    with _poller_lock:
        if _poller_thread and _poller_thread.is_alive() and _poller_token == bot_token:
            return True

        if _poller_stop:
            _poller_stop.set()

        stop_event = threading.Event()
        _poller_stop = stop_event
        _poller_token = bot_token
        _poller_thread = threading.Thread(
            target=_poll_updates,
            args=(bot_token, stop_event),
            name="telegram-local-poller",
            daemon=True,
        )
        _poller_thread.start()
        logger.info("Telegram local polling fallback started.")
        return True


def stop_local_polling() -> None:
    global _poller_stop, _poller_thread, _poller_token
    with _poller_lock:
        if _poller_stop:
            _poller_stop.set()
        _poller_stop = None
        _poller_thread = None
        _poller_token = None


def _poll_updates(bot_token: str, stop_event: threading.Event) -> None:
    delete_webhook(bot_token)
    offset: Optional[int] = None
    while not stop_event.is_set():
        try:
            params: Dict[str, Any] = {
                "timeout": 25,
                "allowed_updates": json.dumps(["message", "callback_query"]),
            }
            if offset is not None:
                params["offset"] = offset
            res = requests.get(telegram_api_url(bot_token, "getUpdates"), params=params, timeout=35)
            if not res.ok:
                logger.warning(f"Telegram getUpdates failed: {res.status_code} {res.text}")
                stop_event.wait(5)
                continue
            data = res.json()
            if not data.get("ok"):
                logger.warning(f"Telegram getUpdates returned not ok: {data}")
                stop_event.wait(5)
                continue
            for update in data.get("result", []):
                update_id = update.get("update_id")
                if isinstance(update_id, int):
                    offset = update_id + 1
                try:
                    from app.api.webhooks import process_telegram_update

                    asyncio.run(process_telegram_update(update))
                except Exception as e:
                    logger.exception(f"Telegram polling update handling failed: {e}")
        except Exception as e:
            logger.warning(f"Telegram local polling failed: {e}")
            stop_event.wait(5)


def send_photo(bot_token: str, chat_id: str, photo_url: str, caption: str,
               reply_markup: Optional[Dict[str, Any]] = None) -> bool:
    """Send a photo with caption + inline keyboard. The image is referenced by
    public URL; Telegram will fetch it. Returns True on success."""
    if not bot_token or not chat_id or not photo_url:
        return False
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": caption[:1024],
        "parse_mode": "HTML",
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        res = requests.post(telegram_api_url(bot_token, "sendPhoto"), data=payload, timeout=30)
        ok = bool(res.ok and res.json().get("ok"))
        if not ok:
            logger.warning(f"Telegram sendPhoto failed: {res.status_code} {res.text}")
        return ok
    except Exception as e:
        logger.warning(f"Telegram sendPhoto error: {e}")
        return False


def send_draft_batch(bot_token: str, chat_id: str, run_id: str, drafts: list) -> bool:
    """Send a Telegram media-group with all draft images, then a follow-up
    message with one inline-keyboard row per idea:

        Idea 1 — Customer case study
            [Approve] [Regenerate] [Dismiss]
        Idea 2 — Founder POV
            [Approve] [Regenerate] [Dismiss]
        Idea 3 — Data snack
            [Approve] [Regenerate] [Dismiss]

    drafts: list of post_drafts rows. Caller is responsible for including one
    row per (idea_index, platform) pair (typically 2 per idea — IG + LI — but
    we group by idea_index here so the user sees one button row per idea).

    Telegram's media-group cannot carry inline_keyboard per-photo, so we send
    the album first, then a separate keyboard message. Both remain in the
    chat reply chain.
    """
    if not bot_token or not chat_id or not drafts:
        return False

    # 1) Media-group with one photo per draft (IG only, to keep the album
    # readable; LinkedIn drafts share the same image so the visual repetition
    # is intentional).
    visible_drafts = [d for d in drafts if d.get("image_url")]
    media = []
    for d in visible_drafts[:10]:  # Telegram caps media-group at 10 items
        idea_idx = d.get("idea_index")
        fmt_label = d.get("format_label") or d.get("format") or ""
        platform = (d.get("platform") or "").title()
        caption = f"<b>Idea {idea_idx} — {fmt_label}</b> · {platform}" if idea_idx else f"<b>{fmt_label}</b> · {platform}"
        media.append({
            "type": "photo",
            "media": d["image_url"],
            "caption": caption[:1024],
            "parse_mode": "HTML",
        })
    if media:
        try:
            res = requests.post(
                telegram_api_url(bot_token, "sendMediaGroup"),
                data={"chat_id": chat_id, "media": json.dumps(media)},
                timeout=30,
            )
            ok = bool(res.ok and res.json().get("ok"))
            if not ok:
                logger.warning(f"Telegram sendMediaGroup failed: {res.status_code} {res.text}")
        except Exception as e:
            logger.warning(f"Telegram sendMediaGroup error: {e}")

    # 2) Follow-up message with the per-idea button matrix.
    by_idea: dict = {}
    for d in drafts:
        idx = d.get("idea_index")
        if not idx:
            continue
        by_idea.setdefault(idx, []).append(d)

    run_prefix = run_id.replace("-", "")[:8]
    rows = []
    for idx in sorted(by_idea.keys()):
        idea_drafts = by_idea[idx]
        # Pick the first draft for callback_data (any of the platforms works;
        # the per-idea action flows through the run_id).
        primary = idea_drafts[0]
        draft_prefix = (primary.get("id") or "").replace("-", "")[:8]
        fmt_label = (primary.get("format_label") or primary.get("format") or "Idea").strip()
        rows.append([
            {"text": f"Approve #{idx}",   "callback_data": f"d:{run_prefix}:{draft_prefix}:approve"},
            {"text": f"Regen #{idx}",     "callback_data": f"d:{run_prefix}:{draft_prefix}:regenerate"},
            {"text": f"Dismiss #{idx}",   "callback_data": f"d:{run_prefix}:{draft_prefix}:dismiss"},
        ])

    keyboard = {"inline_keyboard": rows} if rows else None
    text = f"All three ready. {len(by_idea)} ideas, {len(drafts)} drafts."
    return send_message(bot_token, chat_id, text, reply_markup=keyboard)


def send_message(bot_token: str, chat_id: str, text: str, reply_markup: Optional[Dict[str, Any]] = None) -> Optional[int]:
    """Returns the message_id on success, None on failure. Callers can pass
    that id back through delete_message to clean up the chat."""
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        res = requests.post(telegram_api_url(bot_token, "sendMessage"), data=payload, timeout=10)
        if not res.ok:
            logger.warning(f"Telegram sendMessage failed: {res.status_code} {res.text}")
            return None
        body = res.json()
        if not body.get("ok"):
            logger.warning(f"Telegram sendMessage not-ok: {body}")
            return None
        return body.get("result", {}).get("message_id")
    except Exception as e:
        logger.warning(f"Telegram message send failed: {e}")
        return None


def delete_message(bot_token: str, chat_id: str, message_id: int) -> bool:
    """Delete a message we previously sent. Telegram allows the bot to delete
    its own messages in private chats and in groups where it has admin rights.
    Failure is non-fatal — we just log it."""
    if not bot_token or not chat_id or not message_id:
        return False
    try:
        res = requests.post(
            telegram_api_url(bot_token, "deleteMessage"),
            data={"chat_id": chat_id, "message_id": str(int(message_id))},
            timeout=10,
        )
        if not res.ok:
            logger.warning(f"Telegram deleteMessage failed: {res.status_code} {res.text}")
            return False
        return bool(res.json().get("ok"))
    except Exception as e:
        logger.warning(f"Telegram deleteMessage error: {e}")
        return False


def edit_message_text(bot_token: str, chat_id: str, message_id: int, text: str, reply_markup: Optional[Dict[str, Any]] = None) -> bool:
    """Edit a previously sent message in-place — used to acknowledge the user's selection
    on the same idea-selection card instead of flooding the chat."""
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        res = requests.post(telegram_api_url(bot_token, "editMessageText"), data=payload, timeout=10)
        ok = bool(res.ok and res.json().get("ok"))
        if not ok:
            logger.warning(f"Telegram editMessageText failed: {res.status_code} {res.text}")
        return ok
    except Exception as e:
        logger.warning(f"Telegram edit failed: {e}")
        return False


def send_idea_selection_message(
    bot_token: str,
    chat_id: str,
    run_id: str,
    ideas: list,
) -> bool:
    """Send the 3-ideas card. Each idea is {index, format, format_label, headline, summary}.
    Inline keyboard: Idea 1 / Idea 2 / Idea 3 / All three / Dismiss."""
    if not bot_token or not chat_id:
        return False

    # Plain text only. LLM-generated ideas can contain '<', '&', etc. that
    # break HTML parse_mode and cause the *whole* message to disappear, leaving
    # only the inline keyboard visible. Plain text is always safe.
    lines = ["Pick a post to develop:\n"]
    for idea in ideas:
        idx = idea.get("index")
        format_label = (idea.get("format_label") or idea.get("format") or "").strip()
        headline = (idea.get("headline") or idea.get("angle") or "").strip()
        summary = (idea.get("summary") or "").strip()
        why_matters = (idea.get("why_reader_cares") or "").strip()
        k_conn = (idea.get("kelvin6k_connection") or "").strip()

        if format_label:
            lines.append(f"{idx}. [{format_label}] {headline}")
        else:
            lines.append(f"{idx}. {headline}")
        if summary:
            lines.append(f"   • Summary: {summary}")
        if why_matters:
            lines.append(f"   • Why it matters: {why_matters}")
        if k_conn:
            lines.append(f"   • Connection: {k_conn}")
        lines.append("")

    text = "\n".join(lines).strip()
    if len(text) > 3800:
        text = text[:3800] + "…"


    # Telegram caps callback_data at 64 bytes; a full UUID + JSON envelope blows
    # that. Encode as a compact token: "i:{8-char run prefix}:{choice}" and
    # resolve the full run_id server-side from the callback.
    prefix = run_id.replace("-", "")[:8]
    def _cb(choice: str) -> str:
        return f"i:{prefix}:{choice}"

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "Idea 1", "callback_data": _cb("1")},
                {"text": "Idea 2", "callback_data": _cb("2")},
                {"text": "Idea 3", "callback_data": _cb("3")},
            ],
            [
                {"text": "All three", "callback_data": _cb("all")},
                {"text": "Dismiss", "callback_data": _cb("dismiss")},
            ],
        ]
    }
    return send_message(bot_token, chat_id, text, reply_markup=keyboard)


def build_draft_message(draft: Dict[str, Any], run_id: str) -> Dict[str, Any]:
    platform = (draft.get("platform") or "").title()
    caption = (draft.get("caption") or "").strip()
    format_label = (draft.get("format_label") or "").strip()
    idea_tag = ""
    if draft.get("idea_index"):
        idea_tag = f"  ·  Idea {draft['idea_index']}"
    header_bits = []
    if format_label:
        header_bits.append(format_label)
    if platform:
        header_bits.append(platform)
    header = " — ".join(header_bits) if header_bits else "Draft"
    text = (
        f"<b>{header}{idea_tag}</b>\n\n"
        f"{caption}\n\n"
        f"<b>Run:</b> {run_id}"
    )
    # 64-byte Telegram cap. Use a prefix token instead of the full UUID.
    draft_id = draft.get("id")
    run_prefix = run_id.replace("-", "")[:8]
    draft_prefix = (draft_id or "").replace("-", "")[:8]

    def _cb(action: str) -> str:
        return f"d:{run_prefix}:{draft_prefix}:{action}"

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "Approve", "callback_data": _cb("approve")},
                {"text": "Regenerate", "callback_data": _cb("regenerate")},
                {"text": "Dismiss", "callback_data": _cb("dismiss")},
            ]
        ]
    }
    return {"text": text, "reply_markup": keyboard}
