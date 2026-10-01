"""
Supabase-backed checkpoint store for LangGraph persistent workflow state.
Falls back to in-memory dict when Supabase is not available.
"""
import json
from typing import Optional, Dict, Any
from app.database.supabase_client import get_supabase_client
from app.config.logging import logger

# In-memory fallback when Supabase is unavailable
_memory_store: Dict[str, Any] = {}


def save_checkpoint(run_id: str, state: Dict[str, Any]) -> None:
    supa = get_supabase_client()
    if supa:
        try:
            supa.table("workflow_checkpoints").upsert({
                "run_id": run_id,
                "checkpoint_data": state
            }).execute()
            return
        except Exception as e:
            logger.error(f"Checkpoint save failed for {run_id}: {e}")

    # Fallback to memory
    _memory_store[run_id] = state


def load_checkpoint(run_id: str) -> Optional[Dict[str, Any]]:
    supa = get_supabase_client()
    if supa:
        try:
            result = supa.table("workflow_checkpoints") \
                .select("checkpoint_data") \
                .eq("run_id", run_id) \
                .single() \
                .execute()
            if result.data:
                return result.data["checkpoint_data"]
        except Exception as e:
            logger.error(f"Checkpoint load failed for {run_id}: {e}")

    return _memory_store.get(run_id)
