import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from app.database.supabase_client import get_supabase_client
from app.config.logging import logger

_IN_MEMORY_SUGGESTIONS: List[Dict[str, Any]] = []


def list_pending_suggestions(status: Optional[str] = "pending") -> List[Dict[str, Any]]:
    """List entity suggestions by status ('pending', 'approved', 'ignored', or None for all)."""
    supa = get_supabase_client()
    if supa:
        try:
            q = supa.table("pending_entity_suggestions").select("*").order("created_at", desc=True)
            if status:
                q = q.eq("status", status)
            res = q.execute()
            if res.data is not None:
                return res.data
        except Exception as e:
            logger.warning(f"Failed to query pending_entity_suggestions from Supabase: {e}")

    if status:
        return [s for s in _IN_MEMORY_SUGGESTIONS if s.get("status") == status]
    return list(_IN_MEMORY_SUGGESTIONS)


def add_pending_suggestion(
    entity_type: str,
    name: str,
    context: str,
    source_doc: str
) -> Dict[str, Any]:
    """Store a newly suggested entity extracted from uploaded documents."""
    record = {
        "id": str(uuid.uuid4()),
        "type": entity_type,
        "name": name.strip(),
        "context": context.strip(),
        "source_doc": source_doc.strip(),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    supa = get_supabase_client()
    if supa:
        try:
            supa.table("pending_entity_suggestions").insert(record).execute()
        except Exception as e:
            logger.warning(f"Could not persist pending suggestion to Supabase: {e}")

    # Also keep in local in-memory store
    _IN_MEMORY_SUGGESTIONS.append(record)
    return record


def approve_suggestion(suggestion_id: str) -> Optional[Dict[str, Any]]:
    """Approve a suggestion and append the entity to the human-approved Brand Profile."""
    from app.services.brand_profile import get_brand_profile
    from app.schemas.brand_profile import BrandProfileRequest

    # Find the suggestion
    item = None
    supa = get_supabase_client()
    if supa:
        try:
            res = supa.table("pending_entity_suggestions").select("*").eq("id", suggestion_id).single().execute()
            item = res.data
        except Exception:
            pass

    if not item:
        for s in _IN_MEMORY_SUGGESTIONS:
            if s.get("id") == suggestion_id:
                item = s
                break

    if not item:
        return None

    # Append to Brand Profile in Supabase
    profile = get_brand_profile()
    entity_type = item.get("type", "product").lower()
    entity_name = item.get("name")
    entity_context = item.get("context") or f"3D concrete printing {entity_type}."

    if entity_type == "product":
        prods = list(profile.get("products") or [])
        if not any(p.get("name", "").lower() == entity_name.lower() for p in prods):
            prods.append({"name": entity_name, "one_liner": entity_context})
            profile["products"] = prods
    else:
        projs = list(profile.get("projects") or [])
        if not any(p.get("name", "").lower() == entity_name.lower() for p in projs):
            projs.append({"name": entity_name, "one_liner": entity_context})
            profile["projects"] = projs

    now = datetime.now(timezone.utc).isoformat()
    profile["updated_at"] = now

    if supa:
        try:
            row = {
                "id": "default",
                "company_name": profile.get("company_name", "Kelvin6k"),
                "website": profile.get("website", "https://www.kelvin6k.com/"),
                "industry": profile.get("industry", "Construction 3D Printing"),
                "target_audience": profile.get("target_audience", "Construction engineers"),
                "brand_voice": profile.get("brand_voice", "Technical"),
                "competitors": profile.get("competitors", []),
                "profile_data": profile,
                "updated_at": now
            }
            supa.table("brand_profiles").upsert(row, on_conflict="id").execute()
            try:
                supa.table("pending_entity_suggestions").update({"status": "approved"}).eq("id", suggestion_id).execute()
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Failed to persist approved suggestion: {e}")

    item["status"] = "approved"
    return item


def ignore_suggestion(suggestion_id: str) -> Optional[Dict[str, Any]]:
    """Mark a suggestion as ignored."""
    item = None
    supa = get_supabase_client()
    if supa:
        try:
            supa.table("pending_entity_suggestions").update({"status": "ignored"}).eq("id", suggestion_id).execute()
            res = supa.table("pending_entity_suggestions").select("*").eq("id", suggestion_id).single().execute()
            item = res.data
        except Exception:
            pass

    if not item:
        for s in _IN_MEMORY_SUGGESTIONS:
            if s.get("id") == suggestion_id:
                s["status"] = "ignored"
                item = s
                break

    return item
