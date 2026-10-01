"""
Content Memory Service.
Tracks previously generated and published posts, detects semantic repetition,
and ensures new post candidates do not repeat recent angles or topics.
"""
import math
from typing import List, Dict, Any, Optional, Tuple
from app.schemas.editorial import ContentMemoryItem
from app.services.rag.embedder import EmbeddingProvider
from app.database.supabase_client import get_supabase_client
from app.config.logging import logger


def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


def _token_jaccard(t1: str, t2: str) -> float:
    set1 = set(t1.lower().split())
    set2 = set(t2.lower().split())
    if not set1 or not set2:
        return 0.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union > 0 else 0.0


def retrieve_content_memory(
    candidate_topic: str,
    brand_id: Optional[str] = "default",
    limit: int = 25
) -> List[ContentMemoryItem]:
    """
    Retrieve historical drafts/posts from Supabase and compute similarity
    against the candidate topic/angle.
    """
    supa = get_supabase_client()
    if not supa:
        logger.info("[ContentMemory] No Supabase client; returning empty memory.")
        return []

    try:
        # Fetch recent approved/published/pending drafts
        res = supa.table("post_drafts") \
            .select("id, caption, strategy, reasoning, format, format_label, created_at, status, idea_index") \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        rows = res.data or []
    except Exception as e:
        logger.warning(f"[ContentMemory] Failed to query post_drafts: {e}")
        return []

    if not rows:
        return []

    embedder = EmbeddingProvider()
    candidate_emb = embedder.embed(candidate_topic) if embedder.available else None

    memory_items: List[ContentMemoryItem] = []
    for r in rows:
        caption = r.get("caption") or ""
        strategy = r.get("strategy") or ""
        reasoning = r.get("reasoning") or ""
        format_v = r.get("format") or ""

        # Extract product references
        full_text = f"{caption} {strategy} {reasoning}".lower()
        matched_product = None
        for p in ["aton", "atom", "g.mini", "gmini", "arcus"]:
            if p in full_text:
                matched_product = p.upper()
                break

        # Extract project references
        matched_project = None
        for proj in ["mes", "zoho", "gcc", "arc", "bus stop", "guard room"]:
            if proj in full_text:
                matched_project = proj.upper()
                break

        # Compute similarity
        sim_score = 0.0
        row_text = f"{reasoning} {strategy} {caption[:200]}"
        if candidate_emb and embedder.available:
            row_emb = embedder.embed(row_text)
            if row_emb:
                sim_score = _cosine_similarity(candidate_emb, row_emb)
        else:
            sim_score = _token_jaccard(candidate_topic, row_text)

        # Parse topic/angle from strategy or caption
        topic_line = candidate_topic
        if "topic:" in strategy.lower():
            for line in strategy.split("\n"):
                if line.lower().startswith("topic:"):
                    topic_line = line.split(":", 1)[1].strip()
                    break

        item = ContentMemoryItem(
            id=r.get("id"),
            topic=topic_line,
            core_message=reasoning or (caption[:120] + "..."),
            angle=reasoning or strategy,
            content_type="technical_post",
            format=format_v,
            product=matched_product,
            project=matched_project,
            major_claims=[],
            visual_concept=None,
            published_at=r.get("created_at"),
            similarity_score=round(sim_score, 3)
        )
        memory_items.append(item)

    # Sort descending by similarity
    memory_items.sort(key=lambda x: x.similarity_score or 0.0, reverse=True)
    return memory_items


def check_topic_repetition(
    candidate_topic: str,
    candidate_angle: str,
    memory_items: List[ContentMemoryItem],
    similarity_threshold: float = 0.80
) -> Tuple[bool, float, List[str]]:
    """
    Check if a candidate topic or angle is overly repetitive.
    Returns: (is_repetitive, max_similarity, reasons)
    """
    reasons = []
    max_sim = 0.0
    high_sim_count = 0

    candidate_text = f"{candidate_topic} {candidate_angle}".strip().lower()

    for item in memory_items:
        sim = item.similarity_score or 0.0
        if sim > max_sim:
            max_sim = sim

        if sim >= similarity_threshold:
            high_sim_count += 1
            reasons.append(
                f"High similarity ({round(sim*100)}%) with previous draft: '{item.angle[:80]}…'"
            )

        # Explicit lexical checks for known repetitive topic clusters (e.g. thermal bridge / lattice toolpaths)
        if "thermal" in candidate_text and "lattice" in candidate_text:
            past_text = f"{item.topic} {item.angle or ''}".lower()
            if "thermal" in past_text and "lattice" in past_text:
                high_sim_count += 1
                reasons.append(f"Repeated thermal bridge + lattice toolpath cluster from previous post: {item.id}")

    is_repetitive = (max_sim >= similarity_threshold) or (high_sim_count >= 2)
    return is_repetitive, max_sim, reasons
