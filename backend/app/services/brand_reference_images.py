import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from app.database.supabase_client import get_supabase_client
from app.config.logging import logger

DEFAULT_REFERENCE_IMAGES: List[Dict[str, Any]] = [
    {
        "id": "ref-atom-1",
        "image_url": "https://kdnbwgeofduhkmvbyuul.supabase.co/storage/v1/object/public/brand-assets/products/Atom%20V1.jpeg",
        "linked_to_type": "product",
        "linked_to_name": "ATOM",
        "uploaded_at": "2026-08-12T15:53:52Z"
    },
    {
        "id": "ref-atom-2",
        "image_url": "https://kdnbwgeofduhkmvbyuul.supabase.co/storage/v1/object/public/brand-assets/products/Atom_V2.jpeg",
        "linked_to_type": "product",
        "linked_to_name": "ATOM",
        "uploaded_at": "2026-08-12T15:53:52Z"
    },
    {
        "id": "ref-aton-1",
        "image_url": "https://kdnbwgeofduhkmvbyuul.supabase.co/storage/v1/object/public/brand-assets/products/Aton.jpeg",
        "linked_to_type": "product",
        "linked_to_name": "ATON",
        "uploaded_at": "2026-08-12T15:53:52Z"
    }
]

# In-memory store for newly uploaded images if Supabase table is not yet migrated
_IN_MEMORY_IMAGES: List[Dict[str, Any]] = list(DEFAULT_REFERENCE_IMAGES)


def get_reference_images_for_name(name: str) -> List[str]:
    """Fetch reference image URLs by exact linked_to_name match.
    Queries Supabase brand_reference_images table with automatic in-memory fallback.
    """
    if not name:
        return []

    norm_name = name.strip().lower()
    supa = get_supabase_client()
    if supa:
        try:
            res = supa.table("brand_reference_images").select("image_url, linked_to_name").execute()
            if res.data:
                matches = [
                    r["image_url"] for r in res.data
                    if r.get("linked_to_name", "").strip().lower() == norm_name
                ]
                if matches:
                    return matches
        except Exception as e:
            logger.warning(f"Failed to query brand_reference_images from Supabase, using fallback: {e}")

    # Fallback to local reference list
    return [
        r["image_url"] for r in _IN_MEMORY_IMAGES
        if r.get("linked_to_name", "").strip().lower() == norm_name
    ]


def add_reference_image(image_url: str, linked_to_type: str, linked_to_name: str) -> Dict[str, Any]:
    """Add a new reference image with its linked entity."""
    record = {
        "id": str(uuid.uuid4()),
        "image_url": image_url,
        "linked_to_type": linked_to_type,
        "linked_to_name": linked_to_name,
        "uploaded_at": datetime.now(timezone.utc).isoformat()
    }

    supa = get_supabase_client()
    if supa:
        try:
            supa.table("brand_reference_images").insert(record).execute()
        except Exception as e:
            logger.warning(f"Could not persist reference image to Supabase: {e}")

    _IN_MEMORY_IMAGES.append(record)
    return record


def list_all_reference_images() -> List[Dict[str, Any]]:
    """List all stored brand reference images."""
    supa = get_supabase_client()
    if supa:
        try:
            res = supa.table("brand_reference_images").select("*").order("uploaded_at", desc=True).execute()
            if res.data:
                return res.data
        except Exception:
            pass
    return list(_IN_MEMORY_IMAGES)
