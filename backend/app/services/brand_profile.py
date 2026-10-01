from typing import Any, Dict, Optional, List
from app.database.supabase_client import get_supabase_client
from app.config.logging import logger
from app.config.settings import settings


DEFAULT_PROFILE_ID = "default"

DEFAULT_FLAT_PROFILE: Dict[str, Any] = {
    "id": "default",
    "company_name": "Kelvin6k",
    "website": "https://www.kelvin6k.com/",
    "industry": "Construction 3D Printing / 3D Concrete Printing / Robotic Construction",
    "brand_voice": "Technical, engineering-focused, innovative, confident, practical, and future-oriented",
    "target_audience": "Construction 3D-printing companies, large-scale 3D concrete printing manufacturers, construction 3D-printing engineers, robotics engineers developing 3D-printing systems, concrete and printable-material researchers, structural engineers working on 3D-printed structures, researchers developing 3D-printing techniques, and companies developing 3D-printing hardware, software, materials, and robotic systems for construction.",
    "brand_principle": "Real construction robotics deployed in real environments.",
    "post_length": "medium",
    "image_primary_provider": "openai",
    "image_openai_model": "gpt-image-1-mini",
    "image_openai_quality": "medium",
    "competitors": [
        "ICON", "COBOD", "PERI 3D Construction Printing", "Apis Cor",
        "SQ4D", "CyBe Construction", "WASP", "Contour Crafting"
    ],
    "products": [
        {"name": "ATOM", "one_liner": "Compact polar-based construction 3D-printing robot."},
        {"name": "ATON", "one_liner": "Large-format construction 3D-printing robot."},
        {"name": "G.MINI", "one_liner": "Compact laboratory/research 3D concrete printer."}
    ],
    "projects": [
        {"name": "MES Projects", "one_liner": "Defense/security infrastructure — Guard Rooms, Sentry Posts, Runway infrastructure."},
        {"name": "GCC Bus-Stop Project", "one_liner": "3D-printed urban public transport bus shelter for municipal infrastructure."},
        {"name": "ZOHO Project", "one_liner": "Off-site and on-site sustainable 3D-printed architectural elements for corporate campus."},
        {"name": "THE ARC", "one_liner": "Large-span curved architectural showcase built with robotic precision printing."}
    ],
    "hard_constraints": {
        "never_invent": [
            "Projects", "Clients", "Product specifications", "Product prices",
            "Performance claims", "Cost savings", "Time savings", "Material savings",
            "Founder experiences", "Founder opinions", "Awards", "Certifications",
            "Partnerships", "Project dates", "Project locations", "Machine capabilities"
        ],
        "product_naming": [
            "Preserve ATON and ATOM as separate names.",
            "Do not silently merge product specifications.",
            "Use the exact name associated with the source/reference being used."
        ],
        "unknown_handling": "If the source does not establish a fact, mark it as unknown and do not guess."
    }
}


def get_brand_profile(profile_id: str = DEFAULT_PROFILE_ID) -> Dict[str, Any]:
    """Retrieve the flat Brand Profile from Supabase (or default fallback).
    Guaranteed to return the clean flat schema.
    """
    supa = get_supabase_client()
    if not supa:
        return _apply_env_telegram_settings(DEFAULT_FLAT_PROFILE)

    try:
        res = supa.table("brand_profiles").select("*").eq("id", profile_id).single().execute()
        raw = res.data or {}
        profile_data = raw.get("profile_data") or {}

        # Unpack flat profile from profile_data if available, otherwise build from columns
        flat = dict(DEFAULT_FLAT_PROFILE)
        if isinstance(profile_data, dict) and profile_data.get("company_name"):
            flat.update(profile_data)
        
        # Override with explicit columns if present
        for col in ["company_name", "website", "industry", "target_audience", "brand_voice", "competitors", "instagram_handle", "linkedin_handle", "approval_channel", "telegram_bot_token", "telegram_chat_id", "telegram_webhook_secret", "post_length", "image_primary_provider", "image_openai_model", "image_openai_quality"]:
            if raw.get(col):
                flat[col] = raw[col]
        
        flat["id"] = raw.get("id") or DEFAULT_PROFILE_ID
        return _apply_env_telegram_settings(flat)
    except Exception as e:
        logger.warning(f"Brand profile unavailable, using default: {e}")
        return _apply_env_telegram_settings(DEFAULT_FLAT_PROFILE)


def _apply_env_telegram_settings(profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(profile or DEFAULT_FLAT_PROFILE)
    if settings.TELEGRAM_BOT_TOKEN:
        merged["telegram_bot_token"] = settings.TELEGRAM_BOT_TOKEN
    if settings.TELEGRAM_CHAT_ID:
        merged["telegram_chat_id"] = settings.TELEGRAM_CHAT_ID
    if settings.TELEGRAM_WEBHOOK_SECRET:
        merged["telegram_webhook_secret"] = settings.TELEGRAM_WEBHOOK_SECRET
    if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
        merged["approval_channel"] = merged.get("approval_channel") or "telegram"
    return merged


def format_brand_context(
    profile: Optional[Dict[str, Any]],
    focus_topic: Optional[str] = None,
    for_agent: Optional[str] = None
) -> str:
    """Format the new flat brand profile context cleanly for prompt injection."""
    p = profile or DEFAULT_FLAT_PROFILE

    competitors = ", ".join(p.get("competitors") or []) or "Not provided"
    
    # Products one-liners
    products_list = p.get("products") or []
    products_text = "\n".join([f"  - {prod.get('name')}: {prod.get('one_liner')}" for prod in products_list]) or "  - None specified"

    # Projects one-liners
    projects_list = p.get("projects") or []
    projects_text = "\n".join([f"  - {proj.get('name')}: {proj.get('one_liner')}" for proj in projects_list]) or "  - None specified"

    hard_constraints = p.get("hard_constraints") or {}
    never_invent = ", ".join(hard_constraints.get("never_invent") or [])
    product_naming = "; ".join(hard_constraints.get("product_naming") or [])
    unknown_handling = hard_constraints.get("unknown_handling") or "If unknown, do not guess."

    return f"""COMPANY IDENTITY & VOICE:
Company: {p.get('company_name', 'Kelvin6k')}
Website: {p.get('website', 'https://www.kelvin6k.com/')}
Industry: {p.get('industry', 'Construction 3D Printing & Robotics')}
Brand Voice: {p.get('brand_voice', 'Technical, engineering-focused, innovative, confident, practical, and future-oriented')}
Target Audience: {p.get('target_audience', 'Civil & structural engineers, construction roboticists')}
Brand Principle: {p.get('brand_principle', 'Real construction robotics deployed in real environments.')}
Competitors: {competitors}

PRODUCTS (Names & Core Identity):
{products_text}

PROJECTS (Names & Verified Context):
{projects_text}

HARD CONSTRAINTS & ANTI-HALLUCINATION RULES:
- Never Invent: {never_invent}
- Product Naming: {product_naming}
- Unknown Handling: {unknown_handling}"""
