"""
Agent log helper — writes progress to Supabase agent_logs table and
triggers Supabase Realtime for the frontend timeline.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from app.database.supabase_client import get_supabase_client
from app.config.settings import settings
from app.config.logging import logger


def log_agent_event(
    run_id: str,
    agent: str,
    status: str,
    input_summary: Optional[str] = None,
    output_summary: Optional[str] = None,
    latency_ms: Optional[int] = None,
    tokens_in: Optional[int] = None,
    tokens_out: Optional[int] = None,
    error: Optional[str] = None,
    log_id: Optional[str] = None,
) -> str:
    """Write an agent log row. Returns the log id."""
    lid = log_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    row = {
        "id": lid,
        "run_id": run_id,
        "agent": agent,
        "model": settings.GROQ_MODEL,
        "started_at": now,
        "finished_at": now if status in ("complete", "error") else None,
        "status": status,
        "input_summary": (input_summary or "")[:500],
        "output_summary": (output_summary or "")[:500],
        "latency_ms": latency_ms,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "error": (error or "")[:500] if error else None
    }

    supa = get_supabase_client()
    if supa:
        try:
            supa.table("agent_logs").upsert(row).execute()
        except Exception as e:
            logger.error(f"Failed to write agent_log {lid}: {e}")
    else:
        logger.info(f"[AgentLog] {agent} [{status}] — {output_summary or ''}")

    return lid
