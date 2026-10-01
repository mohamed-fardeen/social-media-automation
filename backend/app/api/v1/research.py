import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import urlparse
import re

from fastapi import APIRouter, HTTPException
from app.schemas.api import ResearchRunRequest, StandardResponse
from app.database.supabase_client import get_supabase_client
from app.schemas.research_plan import ResearchPlan, SocialSearchTarget
from app.services.brand_profile import format_brand_context, get_brand_profile
from app.services.research.router import SourceRouter
from app.config.logging import logger

router = APIRouter()

CONSTRUCTION_3DP_TERMS = (
    "construction 3d printing",
    "3d construction printing",
    "3d printed construction",
    "3d printed building",
    "3d printed home",
    "3d printed house",
    "3d concrete printing",
    "concrete 3d printing",
    "large-scale robotic 3d printing",
    "robotic 3d printing",
    "additive construction",
    "additive manufacturing in construction",
)

TREND_EVENT_TERMS = (
    "new",
    "emerging",
    "launch",
    "launched",
    "unveiled",
    "announced",
    "breakthrough",
    "pilot",
    "project",
    "partnership",
    "regulation",
    "standard",
    "code",
    "market",
    "funding",
    "investment",
    "material",
    "technology",
    "printer",
    "robot",
    "robotic",
    "first",
    "wins",
    "contract",
    "expands",
)

REFERENCE_TERMS = (
    "wikipedia",
    "definition",
    "what is",
    "introduction to",
    "guide to",
    "overview",
    "encyclopedia",
    "educational",
    "course",
    "lesson",
    "background",
)

PUBLISHER_TERMS = (
    "magazine",
    "news",
    "media",
    "journal",
    "blog",
    "channel",
    "podcast",
    "youtube",
    "publisher",
    "press",
)

KNOWN_CONSTRUCTION_3DP_COMPETITORS = (
    "ICON",
    "COBOD",
    "CyBe",
    "WASP",
    "Mighty Buildings",
    "Apis Cor",
    "Black Buffalo 3D",
    "PERI 3D Construction",
    "SQ4D",
    "Alquist 3D",
    "XtreeE",
    "Contour Crafting",
    "Tvasta",
    "MudBots",
    "Constructions-3D",
)


def _list_from_profile(profile: Dict[str, Any] | None, key: str) -> List[str]:
    value = (profile or {}).get(key)
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _scope_terms(country_scope: str) -> tuple[str, str]:
    if country_scope == "india":
        return "India", "in India"
    return "global", "globally"


def _combined_doc_text(doc: Any) -> str:
    return f"{getattr(doc, 'title', '')} {getattr(doc, 'content', '')}".strip()


def _is_in_construction_3dp_scope(text: str) -> bool:
    haystack = text.lower()
    return any(term in haystack for term in CONSTRUCTION_3DP_TERMS)


def _is_reference_source(doc: Any, text: str) -> bool:
    haystack = text.lower()
    host = urlparse(getattr(doc, "url", "") or "").netloc.lower()
    if "wikipedia.org" in host:
        return True
    return any(term in haystack for term in REFERENCE_TERMS)


def _is_publisher_or_media_entity(name: str) -> bool:
    lowered = name.lower()
    return any(term in lowered for term in PUBLISHER_TERMS)


def _competitor_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _extract_competitor_entities(text: str, configured_competitors: List[str]) -> List[str]:
    candidates = [*configured_competitors, *KNOWN_CONSTRUCTION_3DP_COMPETITORS]
    found: Dict[str, str] = {}
    for candidate in candidates:
        name = candidate.strip()
        if not name or _is_publisher_or_media_entity(name):
            continue
        pattern = rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])"
        if re.search(pattern, text, flags=re.IGNORECASE):
            found.setdefault(_competitor_key(name), name)
    return list(found.values())


def _is_trend_content(text: str) -> bool:
    haystack = text.lower()
    return _is_in_construction_3dp_scope(text) and any(term in haystack for term in TREND_EVENT_TERMS)


def _build_research_rows(
    docs: List[Any],
    *,
    company: str,
    topic: str,
    industry: str,
    competitors: List[str],
    now: str,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    seen_competitors: set[str] = set()

    for doc in docs:
        text = _combined_doc_text(doc)
        if not _is_in_construction_3dp_scope(text):
            continue

        source_title = (getattr(doc, "title", "") or f"Research finding for {company}")[:240]
        source_summary = (getattr(doc, "content", "") or f"Source discovered for {topic}")[:900]
        source_url = getattr(doc, "url", "")
        source_provider = getattr(doc, "provider", "")
        source_platform = getattr(doc, "platform", "web")
        base_tags = [source_platform, source_provider, industry][:5]
        competitor_entities = _extract_competitor_entities(text, competitors)
        is_reference = _is_reference_source(doc, text)

        for entity in competitor_entities:
            key = _competitor_key(entity)
            if key in seen_competitors:
                continue
            seen_competitors.add(key)
            rows.append({
                "id": str(uuid.uuid4()),
                "title": entity[:240],
                "summary": f"Competitor entity discussed by source: {source_title}. {source_summary}"[:900],
                "source": source_provider,
                "source_kind": "competitor",
                "url": source_url,
                "tags": [*base_tags, "competitor_entity"][:5],
                "captured_at": now,
                "related_count": 1,
            })

        if is_reference:
            source_kind = "reference"
        elif _is_trend_content(text):
            source_kind = "trend"
        elif competitor_entities:
            source_kind = "reference"
        else:
            source_kind = "reference"

        rows.append({
            "id": str(uuid.uuid4()),
            "title": source_title,
            "summary": source_summary,
            "source": source_provider,
            "source_kind": source_kind,
            "url": source_url,
            "tags": base_tags,
            "captured_at": now,
            "related_count": 1,
        })

    return rows


@router.get("", response_model=StandardResponse)
async def get_research():
    """Return research insights stored during runs."""
    supa = get_supabase_client()
    if not supa:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        res = supa.table("research_insights") \
            .select("*") \
            .order("captured_at", desc=True) \
            .limit(50) \
            .execute()
        return StandardResponse(ok=True, data={"insights": res.data or []})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run", response_model=StandardResponse)
async def run_research(payload: ResearchRunRequest):
    """Run research only. Does not generate drafts."""
    supa = get_supabase_client()
    if not supa:
        raise HTTPException(status_code=503, detail="Database unavailable")

    profile = get_brand_profile()
    brand_context = format_brand_context(profile)
    company = (profile or {}).get("company_name") or "the company"
    industry = (profile or {}).get("industry") or "social media"
    products = (profile or {}).get("products_services") or ""
    topic = payload.topic or (profile or {}).get("goals") or f"{industry} market opportunities"
    platforms = payload.platforms or ["instagram", "linkedin"]
    scope_label, scope_phrase = _scope_terms(payload.country_scope)
    competitors = _list_from_profile(profile, "competitors")
    themes = _list_from_profile(profile, "content_themes")
    market_terms = " ".join(part for part in [industry, products, " ".join(themes[:3])] if part).strip()
    competitor_queries = (
        [f"{name} {industry} {scope_phrase} social media content strategy" for name in competitors[:4]]
        if competitors
        else [
            f"top {industry} companies {scope_phrase}",
            f"{industry} startups competitors {scope_phrase}",
            f"{products or industry} competitors {scope_phrase}",
        ]
    )

    plan = ResearchPlan(
        summary_of_intent=(
            f"Research only for {company}. Use the company name as internal context, not as the primary search target. "
            f"Scope: {scope_label}. Topic: {topic}. Brand context: {brand_context}"
        ),
        web_queries=[
            f"{market_terms or industry} trends {scope_phrase}",
            f"{market_terms or industry} audience demand signals {scope_phrase}",
            *competitor_queries,
        ][:6],
        social_targets=[
            SocialSearchTarget(platform=platform, query_or_handle=f"{industry} {scope_label}")
            for platform in platforms[:2]
        ] + [
            SocialSearchTarget(platform=platform, query_or_handle=f"{name} {industry}")
            for platform in platforms[:3]
            for name in competitors[:2]
        ],
    )

    docs = SourceRouter().execute_plan(plan, max_total_docs=payload.max_results)
    now = datetime.now(timezone.utc).isoformat()
    rows = _build_research_rows(
        docs,
        company=company,
        topic=topic,
        industry=industry,
        competitors=competitors,
        now=now,
    )

    if rows:
        try:
            # Check existing recent insights to prevent duplicates
            existing_res = supa.table("research_insights").select("url,title").order("captured_at", desc=True).limit(100).execute()
            existing_urls = {r.get("url") for r in (existing_res.data or []) if r.get("url")}
            existing_titles = {"".join(c.lower() for c in (r.get("title") or "") if c.isalnum())[:40] for r in (existing_res.data or [])}

            unique_rows = []
            for r in rows:
                norm_t = "".join(c.lower() for c in (r.get("title") or "") if c.isalnum())[:40]
                u = r.get("url")
                if norm_t in existing_titles or (u and u in existing_urls):
                    continue
                existing_titles.add(norm_t)
                if u:
                    existing_urls.add(u)
                unique_rows.append(r)

            if unique_rows:
                supa.table("research_insights").insert(unique_rows).execute()
                logger.info(f"[research] persisted {len(unique_rows)} new unique insights (skipped {len(rows) - len(unique_rows)} duplicates)")
            else:
                logger.info(f"[research] all {len(rows)} insights already exist in database (no duplicates inserted)")
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Could not store research insights. Ensure migration 003_research_insights.sql is applied. {e}"
            )

        for r in (unique_rows if 'unique_rows' in locals() and unique_rows else rows[:5]):
            tag = r.get("source_kind") or "?"
            title = (r.get("title") or "").strip()[:80]
            url = (r.get("url") or "").strip()
            logger.info(f"[research]   [{tag}] {title}  {url}")
    else:
        logger.warning(f"[research] no rows produced for topic={topic!r} scope={payload.country_scope} — check source routers")

    return StandardResponse(ok=True, data={
        "insights": rows,
        "evidence_count": len(docs),
        "brand_context": brand_context,
    })
