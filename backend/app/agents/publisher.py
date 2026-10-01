"""
Publisher Agent — publishes approved drafts to Instagram and LinkedIn.
Records results in publish_results table.
"""
import uuid
import time
from datetime import datetime, timezone
from typing import List
from app.graph.state import RunState
from app.agents.log_helper import log_agent_event
from app.services.publishing.instagram import InstagramProvider
from app.services.publishing.linkedin import LinkedInProvider
from app.database.supabase_client import get_supabase_client
from app.config.logging import logger


def publisher_node(state: RunState) -> RunState:
    run_id = state["run_id"]
    log_id = log_agent_event(run_id, "publisher", "running",
                             input_summary=f"drafts: {state.get('draft_ids')}")
    t0 = time.monotonic()

    supa = get_supabase_client()
    errors = list(state.get("errors", []))

    try:
        ig = InstagramProvider()
        li = LinkedInProvider()
        platforms = state.get("platforms", ["instagram", "linkedin"])
        published_draft_ids: List[str] = []

        for draft_id in state.get("draft_ids", []):
            # Fetch draft
            if supa:
                res = supa.table("post_drafts").select("*").eq("id", draft_id).single().execute()
                draft = res.data if res.data else {}
            else:
                draft = {}

            platform = draft.get("platform") or ""

            if platform == "instagram" and "instagram" in platforms:
                result = ig.publish(
                    caption=draft.get("caption", state.get("instagram_draft", "")),
                    image_url=state.get("image_url") or draft.get("image_url"),
                    hashtags=draft.get("hashtags", state.get("instagram_hashtags", []))
                )
            elif platform == "linkedin" and "linkedin" in platforms:
                result = li.publish(
                    caption=draft.get("caption", state.get("linkedin_draft", "")),
                    image_url=state.get("image_url") or draft.get("image_url"),
                    hashtags=draft.get("hashtags", state.get("linkedin_hashtags", []))
                )
            else:
                continue

            now = datetime.now(timezone.utc).isoformat()
            pub_row = {
                "id": str(uuid.uuid4()),
                "draft_id": draft_id,
                "platform": platform,
                "published_at": now,
                "external_url": result.get("external_url"),
                "status": result.get("status", "failed"),
                "error": result.get("error")
            }

            if supa:
                try:
                    supa.table("publish_results").insert(pub_row).execute()
                    # Mark draft as published
                    supa.table("post_drafts").update({
                        "status": "published",
                        "published_at": now
                    }).eq("id", draft_id).execute()
                except Exception as e:
                    logger.error(f"Failed to record publish result: {e}")

            if result.get("status") in ("success", "simulated"):
                published_draft_ids.append(draft_id)
            else:
                errors.append(f"publish_{platform}: {result.get('error')}")

        latency = int((time.monotonic() - t0) * 1000)
        log_agent_event(run_id, "publisher", "complete",
                        output_summary=f"Published {len(published_draft_ids)} drafts",
                        latency_ms=latency,
                        log_id=log_id)

        # Update run status
        if supa:
            try:
                supa.table("post_runs").update({
                    "status": "published",
                    "finished_at": datetime.now(timezone.utc).isoformat()
                }).eq("id", run_id).execute()
            except Exception as e:
                logger.error(f"Failed to update run status: {e}")

        return {
            **state,
            "status": "published",
            "errors": errors
        }

    except Exception as e:
        logger.error(f"Publisher node failed for run {run_id}: {e}")
        log_agent_event(run_id, "publisher", "error", error=str(e), log_id=log_id)
        return {
            **state,
            "status": "failed",
            "errors": errors + [f"publisher: {e}"]
        }
