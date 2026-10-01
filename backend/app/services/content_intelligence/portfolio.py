"""
Content Portfolio Tracking Service.
Maintains awareness of recent Kelvin6k editorial distribution across Products,
Projects, Technology themes, Industry domains, and Proof levels.
"""
from typing import List, Dict, Any, Optional
from collections import Counter
from app.schemas.editorial import ContentPortfolioSummary
from app.database.supabase_client import get_supabase_client
from app.config.logging import logger


CATEGORIES_KEYWORDS = {
    "products": {
        "ATON": ["aton", "robotic arm", "industrial robot", "6-axis"],
        "ATOM": ["atom", "polar", "rotary", "circular printer"],
        "G.MINI": ["g.mini", "gmini", "compact printer", "mobile printer"],
        "ARCUS": ["arcus", "ecosystem", "multi-robot"]
    },
    "projects": {
        "MES": ["mes", "military engineer", "guard room", "sentry post", "runway"],
        "GCC": ["gcc", "bus stop", "bus-stop", "chennai corporation"],
        "ZOHO": ["zoho", "green building", "sustainable office"],
        "THE ARC": ["the arc", "arc space", "off-site printed"]
    },
    "technology": {
        "robotics": ["robotics", "kinematics", "reach", "payload", "end-effector"],
        "materials": ["geopolymer", "mortar", "aggregate", "hydration", "setting time", "thixotropy"],
        "toolpaths": ["toolpath", "slicing", "bead width", "layer height", "extrusion"],
        "automation": ["autonomous", "sensor", "closed-loop", "feedback"],
        "software": ["software", "digital twin", "simulation", "parametric"]
    },
    "industry": {
        "construction": ["construction", "jobsite", "contractor", "civil engineering"],
        "sustainability": ["sustainability", "carbon", "embodied carbon", "green"],
        "regulation": ["regulation", "building code", "standard", "astm", "compliance"],
        "cost": ["cost", "capex", "opex", "material savings", "roi"],
        "labour": ["labour", "labor", "workforce", "safety", "skilled shortage"],
        "housing": ["housing", "affordable", "urban", "shelter"]
    },
    "proof": {
        "projects": ["built", "site deploy", "commissioned", "installed"],
        "numbers": ["percent", "%", "hours", "sqft", "mpa", "kg"],
        "milestones": ["milestone", "first", "record", "delivered"],
        "case_studies": ["case study", "project review", "field test"],
        "demonstrations": ["demonstration", "benchmark", "prototype"]
    }
}


def get_content_portfolio(brand_id: Optional[str] = "default", limit: int = 30) -> ContentPortfolioSummary:
    """
    Analyzes the last N posts/drafts to compute portfolio category distributions.
    """
    supa = get_supabase_client()
    if not supa:
        return ContentPortfolioSummary()

    try:
        res = supa.table("post_drafts") \
            .select("caption, strategy, reasoning, created_at") \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        rows = res.data or []
    except Exception as e:
        logger.warning(f"[ContentPortfolio] DB query failed: {e}")
        return ContentPortfolioSummary()

    products_count: Counter = Counter()
    projects_count: Counter = Counter()
    tech_count: Counter = Counter()
    industry_count: Counter = Counter()
    proof_count: Counter = Counter()
    recent_topics: List[str] = []

    for row in rows:
        text = f"{row.get('caption', '')} {row.get('strategy', '')} {row.get('reasoning', '')}".lower()
        
        # Track topics
        if row.get("reasoning"):
            recent_topics.append(row.get("reasoning")[:80])

        for prod_name, kws in CATEGORIES_KEYWORDS["products"].items():
            if any(kw in text for kw in kws):
                products_count[prod_name] += 1

        for proj_name, kws in CATEGORIES_KEYWORDS["projects"].items():
            if any(kw in text for kw in kws):
                projects_count[proj_name] += 1

        for tech_name, kws in CATEGORIES_KEYWORDS["technology"].items():
            if any(kw in text for kw in kws):
                tech_count[tech_name] += 1

        for ind_name, kws in CATEGORIES_KEYWORDS["industry"].items():
            if any(kw in text for kw in kws):
                industry_count[ind_name] += 1

        for proof_name, kws in CATEGORIES_KEYWORDS["proof"].items():
            if any(kw in text for kw in kws):
                proof_count[proof_name] += 1

    return ContentPortfolioSummary(
        products_distribution=dict(products_count),
        projects_distribution=dict(projects_count),
        tech_distribution=dict(tech_count),
        industry_distribution=dict(industry_count),
        proof_distribution=dict(proof_count),
        recent_topics=recent_topics[:10]
    )
