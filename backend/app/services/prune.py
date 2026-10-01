from datetime import datetime, timedelta, timezone
from app.database.supabase_client import get_supabase_client
from app.config.logging import logger
import threading

def prune_old_logs(days_old: int = 14):
    """Prunes agent_logs older than days_old to save DB space."""
    supa = get_supabase_client()
    if not supa:
        return
        
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat()
    try:
        # We assume created_at or started_at exists. agent_logs has started_at.
        res = supa.table("agent_logs").delete().lt("started_at", cutoff_date).execute()
        if hasattr(res, 'data') and res.data:
            logger.info(f"Pruned {len(res.data)} old agent logs.")
    except Exception as e:
        logger.warning(f"Failed to prune agent logs: {e}")


def prune_old_runs(days_old: int = 30):
    """Prunes old post_runs (and cascading drafts/logs if set up) older than days_old."""
    supa = get_supabase_client()
    if not supa:
        return
        
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat()
    try:
        # post_runs has created_at
        res = supa.table("post_runs").delete().lt("created_at", cutoff_date).execute()
        if hasattr(res, 'data') and res.data:
            logger.info(f"Pruned {len(res.data)} old post runs.")
    except Exception as e:
        logger.warning(f"Failed to prune post runs: {e}")


def run_pruning_job_async():
    """Runs pruning in a background thread."""
    def job():
        prune_old_logs()
        prune_old_runs()
        
    thread = threading.Thread(target=job, daemon=True)
    thread.start()
