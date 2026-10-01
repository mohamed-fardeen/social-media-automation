from __future__ import annotations

from typing import Any, Dict, Optional
import requests

from app.config.logging import logger
from app.services.telegram_bot import send_message, send_photo, build_draft_message


def build_approval_payload(*, draft: Dict[str, Any], run_id: str, channel: str, contact: Optional[str]) -> Dict[str, Any]:
    return {
        "channel": channel,
        "contact": contact,
        "run_id": run_id,
        "draft_id": draft.get("id"),
        "platform": draft.get("platform"),
        "caption": draft.get("caption"),
        "hashtags": draft.get("hashtags") or [],
        "image_prompt": draft.get("image_prompt"),
        "status": draft.get("status"),
        "actions": [
            {"label": "Approve", "action": "approve"},
            {"label": "Regenerate", "action": "regenerate"},
            {"label": "Dismiss", "action": "reject"},
        ],
    }


def send_approval_notification(
    *,
    bot_token: Optional[str],
    chat_id: Optional[str],
    draft: Dict[str, Any],
    run_id: str,
) -> bool:
    if not bot_token or not chat_id:
        return False

    payload = build_approval_payload(draft=draft, run_id=run_id, channel="telegram", contact=chat_id)
    msg = build_draft_message(draft, run_id)
    caption = msg["text"]
    image_url = draft.get("image_url")

    # Prefer sendPhoto when we have an image, so the generated visual renders
    # inline in Telegram. Fall back to plain text if photo upload fails.
    if image_url:
        try:
            if send_photo(bot_token, chat_id, image_url, caption, reply_markup=msg["reply_markup"]):
                return True
            logger.warning("sendPhoto failed for approval notification — falling back to text.")
        except Exception as e:
            logger.warning(f"sendPhoto error, falling back to text: {e}")

    try:
        return send_message(bot_token, chat_id, caption + "\n\nReply with /approve /regenerate /dismiss.",
                            reply_markup=msg["reply_markup"])
    except Exception as e:
        logger.warning(f"Approval notification error: {e}")
        return False
