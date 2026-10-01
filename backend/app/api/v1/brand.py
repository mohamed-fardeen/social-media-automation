from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from app.schemas.brand_profile import BrandProfileRequest, BrandProfileData
from app.schemas.api import TelegramConnectRequest, StandardResponse
from app.config.settings import settings
from app.database.supabase_client import get_supabase_client
from app.services.brand_profile import DEFAULT_PROFILE_ID, get_brand_profile
from app.services.telegram_bot import verify_bot_token, set_bot_commands, set_webhook, send_message, start_local_polling

router = APIRouter()


@router.get("/profile", response_model=StandardResponse)
async def get_profile():
    profile = get_brand_profile()
    return StandardResponse(ok=True, data={"profile": profile})


@router.put("/profile", response_model=StandardResponse)
async def upsert_profile(payload: BrandProfileRequest):
    supa = get_supabase_client()
    if not supa:
        raise HTTPException(status_code=503, detail="Database unavailable")

    now = datetime.now(timezone.utc).isoformat()
    flat_data = payload.model_dump()
    
    row = {
        "id": DEFAULT_PROFILE_ID,
        "company_name": flat_data.get("company_name"),
        "website": flat_data.get("website"),
        "industry": flat_data.get("industry"),
        "target_audience": flat_data.get("target_audience"),
        "brand_voice": flat_data.get("brand_voice"),
        "competitors": flat_data.get("competitors", []),
        "instagram_handle": flat_data.get("instagram_handle"),
        "linkedin_handle": flat_data.get("linkedin_handle"),
        "approval_channel": flat_data.get("approval_channel", "none"),
        "telegram_bot_token": flat_data.get("telegram_bot_token"),
        "telegram_chat_id": flat_data.get("telegram_chat_id"),
        "telegram_webhook_secret": flat_data.get("telegram_webhook_secret"),
        "profile_data": flat_data,
        "updated_at": now,
    }

    try:
        res = supa.table("brand_profiles").upsert(row, on_conflict="id").execute()
        profile = get_brand_profile()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not save company profile: {e}"
        )

    if profile.get("approval_channel") == "telegram" and profile.get("telegram_bot_token"):
        bot_token = profile.get("telegram_bot_token")
        webhook_secret = profile.get("telegram_webhook_secret")
        public_base = settings.TELEGRAM_PUBLIC_WEBHOOK_BASE
        if verify_bot_token(bot_token):
            set_bot_commands(bot_token)
            if public_base:
                webhook_url = f"{public_base.rstrip('/')}/webhook/telegram/{webhook_secret or 'default'}"
                set_webhook(bot_token, webhook_url, webhook_secret)
            else:
                start_local_polling(bot_token)
        if profile.get("telegram_chat_id"):
            send_message(
                bot_token,
                str(profile.get("telegram_chat_id")),
                "Telegram approval bot connected. You can now use /research, /upload, /draft, and /run.",
            )
    return StandardResponse(ok=True, data={"profile": profile})


@router.post("/telegram/connect", response_model=StandardResponse)
async def connect_telegram(payload: TelegramConnectRequest):
    supa = get_supabase_client()
    if not supa:
        raise HTTPException(status_code=503, detail="Database unavailable")

    now = datetime.now(timezone.utc).isoformat()
    row = {
        "id": DEFAULT_PROFILE_ID,
        "approval_channel": payload.approval_channel or "telegram",
        "telegram_bot_token": payload.telegram_bot_token,
        "telegram_chat_id": payload.telegram_chat_id,
        "telegram_webhook_secret": payload.telegram_webhook_secret,
        "updated_at": now,
    }

    try:
        supa.table("brand_profiles").upsert(row, on_conflict="id").execute()
        profile = get_brand_profile()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save Telegram settings: {e}")

    bot_token = payload.telegram_bot_token
    if verify_bot_token(bot_token):
        set_bot_commands(bot_token)
        public_base = settings.TELEGRAM_PUBLIC_WEBHOOK_BASE
        if public_base:
            webhook_url = f"{public_base.rstrip('/')}/webhook/telegram/{payload.telegram_webhook_secret or 'default'}"
            set_webhook(bot_token, webhook_url, payload.telegram_webhook_secret)
        else:
            start_local_polling(bot_token)
    if payload.telegram_chat_id:
        send_message(
            bot_token,
            str(payload.telegram_chat_id),
            "Telegram approval bot connected. You can now use /research, /upload, /draft, and /run.",
        )
    return StandardResponse(ok=True, data={"profile": profile})
