"""
Copywriter Agent — writes professional, high-density, evidence-grounded B2B copy.
Consumes the EditorialBrief as its sole authoritative source of truth.
Emulates the positioning, credibility, and clarity of leading construction technology firms (COBOD, PERI, CyBe, Tvasta, ICON).
"""
import time
from typing import Dict, Any, List, Optional
from app.graph.state import RunState
from app.agents.log_helper import log_agent_event
from app.services.llm.groq import GroqLLM
from app.schemas.agent_outputs import CopywriterOutput
from app.config.logging import logger
import re

# ── Unicode Bold Conversion ──────────────────────────────────────────────────
# LinkedIn renders Unicode Mathematical Bold Sans-Serif as native bold text.
# We instruct the LLM to use **markdown bold** for structural anchor lines,
# then convert to Unicode at output time so no ** is ever visible.
_BOLD_UPPER = [chr(0x1D5D4 + i) for i in range(26)]
_BOLD_LOWER = [chr(0x1D5EE + i) for i in range(26)]
_BOLD_DIGITS = [chr(0x1D7EC + i) for i in range(10)]

def _char_to_bold(c: str) -> str:
    if 'A' <= c <= 'Z':
        return _BOLD_UPPER[ord(c) - ord('A')]
    if 'a' <= c <= 'z':
        return _BOLD_LOWER[ord(c) - ord('a')]
    if '0' <= c <= '9':
        return _BOLD_DIGITS[ord(c) - ord('0')]
    return c

def apply_unicode_bold(text: str) -> str:
    """Convert **markdown bold** spans to LinkedIn-native Unicode bold characters."""
    return re.sub(r'\*\*(.+?)\*\*', lambda m: ''.join(_char_to_bold(c) for c in m.group(1)), text, flags=re.DOTALL)
# ──────────────────────────────────────────────────


COPYWRITER_SYSTEM_PROMPT = """You are the Lead Technical Copywriter for Kelvin6k — a robotic 3D concrete printing company.
Your job is to write professional, modern, confident, and technically credible LinkedIn posts.

POST STRUCTURE (follow this exact flow every time):
  1. HOOK (1-2 lines): Start with an emoji + bold statement or a sharp technical question that creates curiosity. Must stop the scroll.
  2. TECHNICAL INSIGHT (2-3 short sentences): Explain the concept in simple, accessible language without losing engineering credibility.
  3. KELVIN6K CONNECTION (1-2 sentences): MUST explicitly name a real Kelvin6k machine (ATON, ATOM, G.MINI, ARCUS) or verified project (MES, GCC Bus-Stop, ZOHO, THE ARC) and how it applies this principle.
  4. BROADER IMPACT (1-2 sentences): What does this mean for the industry or engineers reading this?
  5. CLOSING (1 sentence): A strong thought, takeaway, or question that encourages genuine peer-to-peer engagement.

FORMATTING RULES:
- Short, punchy paragraphs with intentional line breaks. Max 2 sentences per paragraph.
- Use 2–5 relevant emojis naturally. Place them at the start of anchor lines ONLY (hook, Kelvin6k connection, closing). NOT at the end of every line.
- Use **bold** ONLY on the 3 structural anchor lines: the hook line, the Kelvin6k connection sentence, and the closing question. Do NOT bold random words inside normal paragraphs.
- Write **bold** using double asterisks exactly as shown. These will be automatically converted to native LinkedIn bold.
- Clean whitespace for mobile readability.

LENGTH CONSTRAINT:
{length_constraint}

HASHTAG RULES:
- Generate 6–10 hashtags total. Mix these categories:
  * Brand hashtags: #Kelvin6k, #ATOM or #ATON (use whichever machine was mentioned)
  * Industry-specific: #Concrete3DPrinting, #ConstructionTechnology, #ConstructionRobotics
  * Broader discovery: #Innovation, #Automation, #FutureOfConstruction, #Robotics, #DigitalConstruction
- Vary the hashtag set per post. Do NOT repeat the exact same hashtags every time.
- Avoid generic or irrelevant hashtags.

BRAND GROUNDING (MANDATORY):
- The post MUST mention at least one specific Kelvin6k product or verified project by name.
- Never write generic industry posts that could belong to any company.
- If the Editorial Brief specifies a product (ATON, ATOM, G.MINI), always use it.

STRICT ANTI-PATTERNS (NEVER DO THESE):
1. NO AI CLICHÉS: Never use "In today's fast-paced world", "Game-changing", "Revolutionary", "Reshapes the landscape", "Delve into".
2. NO HALLUCINATED NUMBERS: ONLY cite stats from the VERIFIED SUPPORTED CLAIMS list. If a number is not there, use qualitative language (e.g. "significantly reduces rework").
3. NO HALLUCINATED FEATURES: Do not invent capabilities, monitoring systems, sensors, or awards. Only use what is in the Editorial Brief.
4. NO BULLET WALLS: Never write lists. Use flowing prose with line breaks instead.
5. NO SALESY CTAS: No "Contact us", "Click here", "Learn more". End with a genuine technical question or insight.
6. NO EMOJI OVERUSE: Max 5 emojis. No emoji at the end of every sentence.

STYLE REFERENCE EXAMPLES:

Example 1:
🏗️ **What if the way a robot moves could reshape the way we build?**

A polar-axis system allows the print head to swivel while the carriage moves radially—creating a more efficient approach to large-scale concrete 3D printing.

By separating angular and linear motion, this geometry can help reduce unnecessary movement and simplify motion control.

🤖 **Kelvin6k's ATOM robot is built around this architecture**, combining a compact footprint with on-site 3D concrete printing capabilities.

For engineers, smarter kinematics can mean rethinking how large-scale robotic systems are designed, controlled, and deployed.

🏗️ **How might smarter robot kinematics reshape the future of construction?**

#Kelvin6k #ATOM #Concrete3DPrinting #ConstructionRobotics #ConstructionTechnology #Innovation

Example 2:
🤖 **Construction is no longer just about machines doing more. It's about machines moving smarter.**

Robotic concrete 3D printing is changing how we think about design, automation, and construction workflows.

From complex geometries to digitally planned toolpaths, technology is opening new possibilities for how structures are built.

🏗️ **Kelvin6k's ATON robot is built for exactly this scale**, with a 12-meter build reach and modular deployment capability.

The future of construction may be built layer by layer—but powered by smarter systems behind every movement.

🛠️ **What construction process do you think robotics will transform next?**

#Kelvin6k #Concrete3DPrinting #Robotics #Automation #DigitalConstruction #FutureOfConstruction

Return structured JSON matching CopywriterOutput.
"""

REGEN_SYSTEM_PROMPT = """You are the Lead Technical Copywriter for Kelvin6k revising a post based on human feedback.

Follow the same style rules as always:
- HOOK → TECHNICAL INSIGHT → KELVIN6K CONNECTION → BROADER IMPACT → CLOSING QUESTION
- Use 2–5 emojis naturally. NO bold text (**) — it looks like AI slop.
- Short micro-paragraphs with generous whitespace.
- {length_constraint_placeholder}
- Address user feedback precisely while keeping factual grounding from the Editorial Brief.
- Professional, peer-to-peer engineering tone. No bullet walls, no AI clichés, no salesy CTAs.
- 6–10 mixed hashtags (brand + industry + discovery).

Return structured JSON matching CopywriterOutput.
"""


def copywriter_node(state: RunState) -> RunState:
    run_id = state["run_id"]
    version = state.get("version", 1)
    feedback = state.get("feedback")
    is_regen = bool(feedback)

    log_id = log_agent_event(run_id, "copywriter", "running",
                             input_summary=f"v{version} {'(regen)' if is_regen else '(initial)'}")
    t0 = time.monotonic()

    from app.services.brand_profile import get_brand_profile
    brand_profile = get_brand_profile(state.get("brand_id", "default"))
    post_length = brand_profile.get("post_length", "medium")

    brief: Dict[str, Any] = state.get("editorial_brief") or {}
    topic = brief.get("topic") or state.get("topic") or "3D Concrete Printing"
    core_message = brief.get("core_message") or state.get("angle") or ""
    why_it_matters = brief.get("why_it_matters") or ""
    kelvin6k_conn = brief.get("kelvin6k_connection") or ""
    supported_claims = brief.get("supported_claims") or []
    unsupported_claims = brief.get("unsupported_claims") or []
    evidence_items = brief.get("evidence") or []
    fmt = brief.get("format") or state.get("format") or "technical_breakdown"

    length_constraint = "- TOTAL LENGTH: 100 to 150 words (550 to 850 characters max). NEVER write long, bloated essay posts."
    if post_length == "short":
        length_constraint = "- TOTAL LENGTH: 50 to 80 words (max 400 characters). 2-3 short sentences total. Ultra-punchy."
    elif post_length == "long":
        length_constraint = "- TOTAL LENGTH: 200+ words. Detailed technical breakdown."

    evidence_str = "\n".join([
        f"- {e.get('claim', '')} (Source: {e.get('source', 'Verified research')})"
        for e in evidence_items
    ]) if evidence_items else "- Grounded in verified 3DCP principles."

    supported_str = "\n".join([f"- {c}" for c in supported_claims]) if supported_claims else f"- {core_message}"
    unsupported_str = "\n".join([f"- {c}" for c in unsupported_claims]) if unsupported_claims else "(none noted)"

    user_prompt = f"""
=== EDITORIAL BRIEF ===
Topic: {topic}
Core Message: {core_message}
Why It Matters: {why_it_matters}
Kelvin6k Connection: {kelvin6k_conn}
Format: {fmt}
Tone: {brief.get('tone', 'Authoritative, concise, engineering-focused B2B')}

=== VERIFIED SUPPORTED CLAIMS (YOU MAY ASSERT THESE) ===
{supported_str}

=== UNVERIFIED / PROHIBITED CLAIMS (DO NOT ASSERT THESE) ===
{unsupported_str}

=== EVIDENCE ===
{evidence_str}
"""

    if is_regen:
        user_prompt += f"""
=== PREVIOUS LINKEDIN DRAFT ===
{state.get('linkedin_draft', '')}

=== USER FEEDBACK TO ADDRESS ===
{feedback}

Write an improved LinkedIn post addressing every point of the feedback precisely.
"""
    else:
        user_prompt += """
Write the platform-native LinkedIn post following the Editorial Brief and strict B2B clarity rules.
"""

    try:
        llm = GroqLLM()
        
        system = REGEN_SYSTEM_PROMPT if is_regen else COPYWRITER_SYSTEM_PROMPT.format(length_constraint=length_constraint)
        
        output: CopywriterOutput = llm.structured(
            system_prompt=system,
            user_prompt=user_prompt,
            schema=CopywriterOutput,
            temperature=0.65
        )

        if output and output.linkedin_post:
            linkedin_draft = apply_unicode_bold(output.linkedin_post.strip())
            linkedin_hashtags = output.linkedin_hashtags or ["#3DConcretePrinting", "#ConstructionRobotics", "#CivilEngineering"]
            instagram_draft = output.instagram_caption or linkedin_draft
            instagram_hashtags = output.instagram_hashtags or linkedin_hashtags
            cta = output.cta or ""
            reasoning = output.reasoning or "Crafted from Editorial Brief with strict claim grounding."
            out_supported = output.supported_claims or supported_claims
            out_unsupported = output.unsupported_claims or unsupported_claims
        else:
            linkedin_draft = f"{core_message}\n\nIn modern construction, {why_it_matters.lower()}.\n\n{kelvin6k_conn}"
            linkedin_hashtags = ["#3DConcretePrinting", "#ConstructionRobotics", "#Automation"]
            instagram_draft = linkedin_draft
            instagram_hashtags = linkedin_hashtags
            cta = ""
            reasoning = "Deterministic brief-grounded fallback."
            out_supported = supported_claims
            out_unsupported = unsupported_claims

        latency = int((time.monotonic() - t0) * 1000)
        log_agent_event(run_id, "copywriter", "complete",
                        output_summary=f"Draft v{version} written ({len(linkedin_draft)} chars)",
                        latency_ms=latency,
                        log_id=log_id)

        return {
            **state,
            "linkedin_draft": linkedin_draft,
            "linkedin_hashtags": linkedin_hashtags,
            "instagram_draft": instagram_draft,
            "instagram_hashtags": instagram_hashtags,
            "cta": cta,
            "notes": reasoning,
            "status": "designing",
            "feedback": None
        }

    except Exception as e:
        logger.error(f"[copywriter_node] Failed for run {run_id}: {e}")
        log_agent_event(run_id, "copywriter", "error", error=str(e), log_id=log_id)
        return {
            **state,
            "linkedin_draft": f"{topic}\n\n{core_message}\n\n{kelvin6k_conn}",
            "linkedin_hashtags": ["#3DConcretePrinting", "#ConstructionTechnology"],
            "instagram_draft": f"{topic} — {core_message}",
            "instagram_hashtags": ["#3DConcretePrinting"],
            "errors": state.get("errors", []) + [f"copywriter: {e}"]
        }
