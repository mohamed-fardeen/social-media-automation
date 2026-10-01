from fastapi import APIRouter, HTTPException
from app.schemas.api import StandardResponse
from app.database.supabase_client import get_supabase_client

router = APIRouter()


@router.get("", response_model=StandardResponse)
async def get_analytics():
    """Return simple analytics summary from published drafts."""
    supa = get_supabase_client()
    if not supa:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        runs_res = supa.table("post_runs").select("status").execute()
        drafts_res = supa.table("post_drafts").select("status, platform").execute()

        runs = runs_res.data or []
        drafts = drafts_res.data or []

        published = [d for d in drafts if d["status"] == "published"]

        return StandardResponse(ok=True, data={
            "total_runs": len(runs),
            "published_posts": len(published),
            "instagram_published": len([d for d in published if d["platform"] == "instagram"]),
            "linkedin_published": len([d for d in published if d["platform"] == "linkedin"]),
            "pending_approval": len([d for d in drafts if d["status"] == "pending_approval"])
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
