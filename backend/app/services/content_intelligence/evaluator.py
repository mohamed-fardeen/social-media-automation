"""
Content Opportunity Evaluator.
Evaluates research signals and candidate angles against strict B2B criteria,
scoring relevance, novelty, evidence strength, brand fit, audience value, and credibility risk.
"""
import json
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from app.schemas.editorial import ContentOpportunity, ContentMemoryItem, ContentPortfolioSummary
from app.services.llm.groq import GroqLLM
from app.config.logging import logger


OPPORTUNITY_EVALUATION_SYSTEM_PROMPT = """You are a senior Content Intelligence Director for Kelvin6k (robotic 3D concrete printing).
Your job is to critically evaluate candidate post opportunities from research findings and brand knowledge.

CRITICAL DIRECTIVE:
You must NOT treat every research finding as a valid post opportunity.
Reject weak, generic, repetitive, or ungrounded topics (e.g. "3D printing is growing", "benefits of automation", "AI in construction").
Accept only topics that have high technical specificity, clear evidence, strong Kelvin6k relevance, and high value to structural engineers and builders.

For each candidate, score from 1.0 to 10.0:
1. relevance: Relevance to 3D concrete printing, materials, robotics, toolpaths, or jobsite deployment.
2. novelty: Freshness of the perspective/development vs standard industry chatter.
3. evidence_strength: Presence of concrete technical data, verified metrics, or real project facts.
4. audience_value: Practical takeaway for structural engineers, contractors, or roboticists.
5. specificity: Deep engineering detail vs superficial platitudes.
6. brand_fit: Logical connection to Kelvin6k machines (ATON, ATOM, G.MINI) or verified projects (MES, ZOHO, GCC, THE ARC).
7. visual_potential: Ability to create clear physical visual proof (layer striations, printhead, structure).
8. credibility_risk: Risk of unsubstantiated claims or overpromising (1 = zero risk, 10 = extreme risk).

Decision rules:
- ACCEPT: overall_score >= 7.5 AND credibility_risk <= 4.0 AND evidence_strength >= 6.0
- NARROW: overall_score >= 6.0 BUT topic is too broad — specify how to narrow it in reasoning
- REJECT: overall_score < 6.0 OR credibility_risk > 6.0 OR evidence_strength < 5.0 OR repetition is high

Return JSON matching:
{
  "opportunities": [
    {
      "topic": "...",
      "relevance": 8.5,
      "novelty": 8.0,
      "evidence_strength": 8.5,
      "audience_value": 8.0,
      "specificity": 8.5,
      "brand_fit": 9.0,
      "visual_potential": 7.5,
      "credibility_risk": 2.0,
      "overall_score": 8.3,
      "reasoning": "...",
      "decision": "ACCEPT|REJECT|NARROW"
    }
  ]
}"""


class _OpportunityList(BaseModel):
    opportunities: List[ContentOpportunity] = Field(default_factory=list)


def evaluate_content_opportunities(
    research_context: str,
    knowledge_context: str,
    topic_hint: Optional[str] = None,
    memory_items: Optional[List[ContentMemoryItem]] = None,
    portfolio_summary: Optional[ContentPortfolioSummary] = None,
    max_candidates: int = 4
) -> List[ContentOpportunity]:
    """
    Evaluates research and candidate topics, producing structured ContentOpportunity scores.
    """
    memory_notes = []
    if memory_items:
        for item in memory_items[:5]:
            sim = round((item.similarity_score or 0.0) * 100)
            memory_notes.append(f"- Past post '{item.angle[:60]}…' (Similarity: {sim}%, Format: {item.format})")
    memory_str = "\n".join(memory_notes) if memory_notes else "No recent similar posts recorded."

    portfolio_notes = []
    if portfolio_summary:
        if portfolio_summary.products_distribution:
            portfolio_notes.append(f"Recent products covered: {portfolio_summary.products_distribution}")
        if portfolio_summary.projects_distribution:
            portfolio_notes.append(f"Recent projects covered: {portfolio_summary.projects_distribution}")
    portfolio_str = "; ".join(portfolio_notes) if portfolio_notes else "Portfolio balanced."

    user_prompt = f"""
CANDIDATE TOPIC HINT: {topic_hint or 'Latest verified 3D concrete printing development'}

RESEARCH CONTEXT:
{research_context[:2500] if research_context else 'No external research available.'}

BRAND KNOWLEDGE & GROUNDING:
{knowledge_context[:1500] if knowledge_context else 'No brand knowledge chunks.'}

RECENT CONTENT MEMORY (Check for repetition!):
{memory_str}

PORTFOLIO DISTRIBUTION:
{portfolio_str}

Evaluate the candidate topics and extract the top {max_candidates} opportunities.
Strictly reject repetitive or generic topics. Return structured JSON.
"""
    llm = GroqLLM()
    opportunities: List[ContentOpportunity] = []

    # Attempt 1: Native Structured Output (Groq JSON Mode)
    try:
        struct_res = llm.structured(
            system_prompt=OPPORTUNITY_EVALUATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema=_OpportunityList,
            temperature=0.2
        )
        if struct_res and isinstance(struct_res, _OpportunityList) and struct_res.opportunities:
            logger.info(f"[OpportunityEvaluator] Successfully parsed {len(struct_res.opportunities)} opportunities via native structured output.")
            return struct_res.opportunities
    except Exception as struct_err:
        logger.warning(f"[OpportunityEvaluator] Native structured output failed ({struct_err}). Attempting fallback chat parsing...")

    # Attempt 2: Gemini failover with JSON mode
    try:
        from app.services.llm.gemini import GeminiLLM
        gemini_llm = GeminiLLM()
        raw = gemini_llm.chat(
            system_prompt=OPPORTUNITY_EVALUATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.2
        )
        raw_clean = re.sub(r"```json\s*|\s*```", "", raw).strip()
        parsed = json.loads(raw_clean)
        raw_opps = parsed.get("opportunities") if isinstance(parsed, dict) else parsed

        if isinstance(raw_opps, list):
            for item in raw_opps:
                try:
                    rel = float(item.get("relevance", 7.0))
                    nov = float(item.get("novelty", 7.0))
                    ev = float(item.get("evidence_strength", 7.0))
                    aud = float(item.get("audience_value", 7.0))
                    spec = float(item.get("specificity", 7.0))
                    bf = float(item.get("brand_fit", 7.0))
                    vis = float(item.get("visual_potential", 7.0))
                    risk = float(item.get("credibility_risk", 3.0))

                    overall = (
                        (rel * 0.20) + (nov * 0.15) + (ev * 0.20) +
                        (aud * 0.15) + (spec * 0.10) + (bf * 0.15) +
                        (vis * 0.05) - (risk * 0.10)
                    )
                    overall = max(1.0, min(10.0, round(overall, 1)))

                    decision = item.get("decision", "ACCEPT").upper()
                    if overall < 6.0 or risk > 6.0:
                        decision = "REJECT"

                    opp = ContentOpportunity(
                        topic=str(item.get("topic") or topic_hint or "3DCP Innovation"),
                        relevance=rel,
                        novelty=nov,
                        evidence_strength=ev,
                        audience_value=aud,
                        specificity=spec,
                        brand_fit=bf,
                        visual_potential=vis,
                        credibility_risk=risk,
                        overall_score=float(item.get("overall_score") or overall),
                        reasoning=str(item.get("reasoning") or "Evaluated based on technical evidence and B2B brand fit."),
                        decision=decision
                    )
                    opportunities.append(opp)
                except Exception as parse_err:
                    logger.warning(f"[OpportunityEvaluator] Item parse error: {parse_err}")

    except Exception as e:
        logger.warning(f"[OpportunityEvaluator] Gemini evaluation failed: {e}. Building deterministic fallback.")

    if not opportunities:
        # Fallback opportunity marked with fallback_heuristic flag
        base_topic = topic_hint or "Robotic concrete deposition control"
        logger.warning(f"[OpportunityEvaluator] [FALLBACK ACTIVE] Scored opportunities using deterministic heuristic.")
        opportunities.append(
            ContentOpportunity(
                topic=base_topic,
                relevance=8.5,
                novelty=7.5,
                evidence_strength=8.0,
                brand_fit=8.5,
                audience_value=8.0,
                specificity=8.0,
                visual_potential=8.0,
                credibility_risk=2.0,
                overall_score=8.1,
                reasoning="[scored_by: fallback_heuristic] Directly grounded in robotic construction and Kelvin6k core capabilities.",
                decision="ACCEPT"
            )
        )

    # Sort descending by overall_score
    opportunities.sort(key=lambda x: x.overall_score, reverse=True)
    return opportunities
