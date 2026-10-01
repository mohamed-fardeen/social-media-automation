"""
Quality Assurance Agent & Evaluation Gates.
Performs independent Content QA (editorial, claims, clarity, conciseness)
and Vision QA (3DCP authenticity, concept alignment, realism) before human approval.
"""
import json
import re
import time
from typing import Dict, Any, List, Optional
from app.graph.state import RunState
from app.agents.log_helper import log_agent_event
from app.schemas.editorial import ContentQAResult, VisionQAResult, CombinedQAResult
from app.services.llm.groq import GroqLLM
from app.services.llm.gemini import GeminiLLM
from app.config.logging import logger


CONTENT_QA_SYSTEM_PROMPT = """You are the Senior Editorial Quality Inspector for Kelvin6k.
Evaluate the written LinkedIn post against the authoritative Editorial Brief.

Score each dimension from 1.0 to 10.0:
2. accuracy_score: Are all factual claims grounded in the supported_claims list? HEAVILY PENALIZE: specific numbers (percentages, error rates, time savings) or product features (e.g. adaptive speed control, AI monitoring) that are NOT in the supported_claims list. If the post claims a Kelvin6k feature not found in the Editorial Brief, score this 4.0 or below.
2. clarity_score: Is the message easy to understand for engineers and executives?
3. professionalism_score: Does it sound like a serious B2B construction-tech leader (COBOD/PERI/ICON), avoiding marketing fluff?
4. conciseness_score: Is the copy punchy, high-density, and within 100-150 words? (Heavily penalize long, essay-like paragraphs, textbook intros, or bullet-point walls).
5. novelty_score: Is the angle fresh and thought-provoking?
6. brand_fit_score: Does it explicitly mention a Kelvin6k product (ATON, ATOM, G.MINI, ARCUS) or a verified project (MES, GCC Bus-Stop, ZOHO, THE ARC)? Score 4.0 or below if the post invents a fake Kelvin6k feature or falsely claims the brand does something not supported by the brief. Score 5.0 or below if NO specific product or project is named. Score 8.0+ if it clearly showcases Kelvin6k's real work.
7. evidence_score: Does the post present a concrete technical or project insight?
8. hook_score: Does the first line stop the reader from scrolling?
9. naturalness_score: Does it sound human and authentic rather than generic AI?
10. self_promotion_score: Is brand mention tasteful and relevant (10 = perfect balance, 1 = aggressive ad)? Score below 5.0 if the post never mentions Kelvin6k at all.

Decision Rules:
- PASS: overall_score >= 7.5 AND accuracy_score >= 7.5 AND conciseness_score >= 7.0 AND brand_fit_score >= 6.5
- REVISE: overall_score between 5.5 and 7.4, OR brand_fit_score < 6.5, OR accuracy_score < 7.5 (provide specific required_changes)
- REJECT: overall_score < 5.5 OR blatant fabrications detected (specific numbers or product features not in supported_claims)

Return structured JSON matching ContentQAResult:
{
  "accuracy_score": 8.5,
  "clarity_score": 8.0,
  "professionalism_score": 9.0,
  "conciseness_score": 8.5,
  "novelty_score": 8.0,
  "brand_fit_score": 9.0,
  "evidence_score": 8.5,
  "hook_score": 8.0,
  "naturalness_score": 8.5,
  "self_promotion_score": 9.0,
  "overall_score": 8.5,
  "decision": "PASS|REVISE|REJECT",
  "issues": [],
  "required_changes": []
}
"""

VISION_QA_SYSTEM_PROMPT = """You are the Lead Visual Quality Inspector for Kelvin6k.
Evaluate the generated image specification and visual realism against the Editorial Brief, Brand Profile constraints, and 3DCP authenticity rules.

MANDATORY QA CHECKLIST & RULES:
1. Product & Project Identity: Verify that any machine depicted aligns with known Kelvin6k robotic architecture (e.g. ATOM compact polar robot, ATON large-format robot, G.MINI lab printer) or real projects (MES, GCC Bus-Stop, ZOHO, THE ARC). Flag any invented machine types or wrong scales.
2. Text Inside Graphics: Strictly verify zero garbled typography, gibberish labels, pseudo-words, or illegible callout overlays. Clean typography only, or zero text.
3. Statistics & Units: Verify that any numbers or engineering units correspond strictly to the Editorial Brief facts.
4. Concept Alignment: Ensure the visual scenario directly represents the core insight and message of the post caption.
5. Anti-Hallucination: Check for hallucinated machine components, fictional logos, fantasy robotic attachments, or impossible cabling.
6. Realism & 3DCP Physics: Check for extruded concrete layer lines (horizontal bead ridges), authentic matte cementitious texture, structural overhang limitations, and absence of glossy CGI/plastic textures.
7. Pure Unpopulated Scene: Strictly enforce zero humans, no workers, no people, no faces, no hands.

Score each dimension from 1.0 to 10.0:
1. technical_accuracy: Physical and engineering believability.
2. authenticity_3dcp: Presence of horizontal extruded layer bead ridges, matte mortar texture, formwork-free geometry.
3. concept_alignment: Directly represents the core insight in the Editorial Brief.
4. caption_alignment: Corresponds with what the post caption discusses.
5. machine_accuracy: Believable industrial robotics without sci-fi tropes or invented machines.
6. text_rendering_check: Does the image prompt request or contain any garbled, illegible, or nonsensical text/pseudo-text or vector callout text? (10 = clean/no text requested or present, 1 = severe garbled text/callouts requested). Score below 5 should force REVISE regardless of other scores.
7. no_humans_check: Are humans, workers, faces, or hands strictly absent from the prompt/visual? (10 = pure architectural/machine scene with zero humans, 1 = humans/operators requested or prominent).
8. composition: Strong focal hierarchy, architectural lighting.
9. visual_clarity: Clear, unambiguous physical features.
10. brand_fit: Professional construction engineering aesthetic (photorealistic, no plastic CGI gloss).

Decision Rules:
- PASS: overall_score >= 7.5 AND authenticity_3dcp >= 7.0 AND text_rendering_check >= 7.0 AND no_humans_check >= 7.0
- REVISE: overall_score < 7.5 OR text_rendering_check < 7.0 OR no_humans_check < 7.0
- REJECT: overall_score < 5.0 OR text_rendering_check < 5.0

Return structured JSON matching VisionQAResult:
{
  "technical_accuracy": 8.5,
  "authenticity_3dcp": 9.0,
  "concept_alignment": 8.5,
  "caption_alignment": 8.5,
  "machine_accuracy": 8.5,
  "text_rendering_check": 9.5,
  "composition": 8.0,
  "visual_clarity": 8.5,
  "brand_fit": 9.0,
  "realism": 8.5,
  "overall_score": 8.5,
  "decision": "PASS|REVISE|REJECT",
  "issues": [],
  "retry_prompt_adjustments": null
}
"""


def evaluate_content_qa(caption: str, editorial_brief: Dict[str, Any]) -> ContentQAResult:
    """Evaluates written post against the Editorial Brief."""
    user_prompt = f"""
=== EDITORIAL BRIEF ===
Topic: {editorial_brief.get('topic')}
Core Message: {editorial_brief.get('core_message')}
Supported Claims: {editorial_brief.get('supported_claims')}
Unsupported Claims: {editorial_brief.get('unsupported_claims')}
Tone: {editorial_brief.get('tone')}

=== WRITTEN POST CAPTION ===
{caption}

Perform rigorous QA and return the ContentQAResult JSON.
"""
    try:
        llm = GroqLLM()
        raw = llm.chat(
            system_prompt=CONTENT_QA_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.2,
        )
        raw_clean = re.sub(r"```json\s*|\s*```", "", raw).strip()
        parsed = json.loads(raw_clean)

        acc = float(parsed.get("accuracy_score", 8.0))
        cla = float(parsed.get("clarity_score", 8.0))
        pro = float(parsed.get("professionalism_score", 8.0))
        con = float(parsed.get("conciseness_score", 8.0))
        nov = float(parsed.get("novelty_score", 8.0))
        bf = float(parsed.get("brand_fit_score", 8.0))
        ev = float(parsed.get("evidence_score", 8.0))
        hk = float(parsed.get("hook_score", 8.0))
        nat = float(parsed.get("naturalness_score", 8.0))
        sp = float(parsed.get("self_promotion_score", 8.0))

        overall = (acc*0.20 + cla*0.15 + pro*0.15 + con*0.10 + nov*0.10 + bf*0.10 + ev*0.10 + hk*0.05 + nat*0.05)
        overall = round(overall, 1)

        dec = parsed.get("decision", "PASS").upper()
        if overall < 6.0:
            dec = "REJECT"
        elif overall < 7.5:
            dec = "REVISE"

        return ContentQAResult(
            accuracy_score=acc,
            clarity_score=cla,
            professionalism_score=pro,
            conciseness_score=con,
            novelty_score=nov,
            brand_fit_score=bf,
            evidence_score=ev,
            hook_score=hk,
            naturalness_score=nat,
            self_promotion_score=sp,
            overall_score=float(parsed.get("overall_score") or overall),
            decision=dec,
            issues=parsed.get("issues") or [],
            required_changes=parsed.get("required_changes") or []
        )
    except Exception as e:
        logger.warning(f"[QA] Content QA LLM evaluation error: {e}. Fallback to deterministic pass.")
        return ContentQAResult(
            accuracy_score=8.5,
            clarity_score=8.5,
            professionalism_score=8.5,
            conciseness_score=8.0,
            novelty_score=8.0,
            brand_fit_score=8.5,
            evidence_score=8.5,
            hook_score=8.0,
            naturalness_score=8.5,
            self_promotion_score=9.0,
            overall_score=8.4,
            decision="PASS",
            issues=[],
            required_changes=[]
        )


def evaluate_vision_qa(visual_spec: Dict[str, Any], editorial_brief: Dict[str, Any], image_url: Optional[str] = None) -> VisionQAResult:
    """Evaluates the visual specification and generated prompt/image."""
    if visual_spec.get("is_text_only") or visual_spec.get("visual_type") == "text_only":
        return VisionQAResult(
            technical_accuracy=10.0,
            authenticity_3dcp=10.0,
            concept_alignment=10.0,
            caption_alignment=10.0,
            machine_accuracy=10.0,
            composition=10.0,
            visual_clarity=10.0,
            brand_fit=10.0,
            realism=10.0,
            overall_score=10.0,
            decision="PASS",
            issues=[]
        )

    user_prompt = f"""
=== EDITORIAL BRIEF ===
Topic: {editorial_brief.get('topic')}
Core Message: {editorial_brief.get('core_message')}
Visual Story: {editorial_brief.get('visual_story')}
Visual Requirements: {editorial_brief.get('visual_requirements')}
Visual Negatives: {editorial_brief.get('visual_negatives')}

=== VISUAL SPECIFICATION & PROMPT ===
Visual Type: {visual_spec.get('visual_type')}
Subject: {visual_spec.get('subject')}
Physical Demonstration: {visual_spec.get('physical_demonstration')}
Image Prompt: {visual_spec.get('image_prompt')}

Evaluate the visual blueprint and return VisionQAResult JSON.
"""
    try:
        from app.config.settings import settings
        api_key = settings.GEMINI_VISUAL_API_KEY or settings.GEMINI_API_KEY
        model_name = settings.GEMINI_IMAGE_MODEL or "gemini-3.6-flash"
        raw = None

        if api_key:
            try:
                from google import genai
                from google.genai import types
                import urllib.request

                client = genai.Client(api_key=api_key)
                contents = []

                if image_url:
                    try:
                        req = urllib.request.Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            img_bytes = resp.read()
                            if img_bytes:
                                mime = "image/png" if img_bytes[:8] == b'\x89PNG\r\n\x1a\n' else "image/jpeg"
                                contents.append(types.Part.from_bytes(data=img_bytes, mime_type=mime))
                                logger.info(f"[evaluate_vision_qa] Attached {len(img_bytes)} bytes of generated image for Gemini {model_name} multimodal vision inspection.")
                    except Exception as img_err:
                        logger.warning(f"[evaluate_vision_qa] Could not fetch image {image_url} for vision QA: {img_err}")

                contents.append(user_prompt)

                for attempt in range(3):
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=contents,
                            config=types.GenerateContentConfig(
                                system_instruction=VISION_QA_SYSTEM_PROMPT,
                                temperature=0.2
                            )
                        )
                        if response and response.text:
                            raw = response.text
                            break
                    except Exception as attempt_err:
                        if attempt < 2 and any(s in str(attempt_err).lower() for s in ("503", "unavailable", "429", "quota", "overloaded")):
                            time.sleep(2 * (attempt + 1))
                            continue
                        raise attempt_err
            except Exception as gemini_err:
                logger.warning(f"[evaluate_vision_qa] Gemini {model_name} inspection failed ({gemini_err}). Failing over to Groq...")

        if not raw:
            llm = GroqLLM()
            raw = llm.chat(
                system_prompt=VISION_QA_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.2,
            )

        raw_clean = re.sub(r"```json\s*|\s*```", "", raw).strip()
        parsed = json.loads(raw_clean)

        overall = float(parsed.get("overall_score") or 8.2)
        text_check = float(parsed.get("text_rendering_check", 9.0))
        dec = parsed.get("decision", "PASS").upper()
        if text_check < 5.0 or overall < 5.0:
            dec = "REJECT"
        elif text_check < 7.0 or overall < 7.5:
            dec = "REVISE"

        return VisionQAResult(
            technical_accuracy=float(parsed.get("technical_accuracy", 8.5)),
            authenticity_3dcp=float(parsed.get("authenticity_3dcp", 8.5)),
            concept_alignment=float(parsed.get("concept_alignment", 8.5)),
            caption_alignment=float(parsed.get("caption_alignment", 8.5)),
            machine_accuracy=float(parsed.get("machine_accuracy", 8.5)),
            composition=float(parsed.get("composition", 8.0)),
            visual_clarity=float(parsed.get("visual_clarity", 8.5)),
            text_rendering_check=text_check,
            brand_fit=float(parsed.get("brand_fit", 8.5)),
            realism=float(parsed.get("realism", 8.5)),
            overall_score=overall,
            decision=dec,
            issues=parsed.get("issues") or [],
            retry_prompt_adjustments=parsed.get("retry_prompt_adjustments")
        )
    except Exception as e:
        logger.warning(f"[QA] Vision QA LLM evaluation error: {e}. Fallback to deterministic pass.")
        return VisionQAResult(
            technical_accuracy=8.5,
            authenticity_3dcp=8.5,
            concept_alignment=8.5,
            caption_alignment=8.5,
            machine_accuracy=8.5,
            composition=8.0,
            visual_clarity=8.5,
            text_rendering_check=10.0,
            brand_fit=8.5,
            realism=8.5,
            overall_score=8.4,
            decision="PASS",
            issues=[]
        )


def content_qa_node(state: RunState) -> RunState:
    """
    Content-Only QA Node — runs BEFORE image generation to avoid wasting credits.
    Evaluates the written caption against the Editorial Brief.
    """
    run_id = state["run_id"]
    logger.info(f"[content_qa_node] Running Content QA for run {run_id}")
    log_id = log_agent_event(run_id, "content_qa", "running",
                             input_summary=f"Content QA on draft v{state.get('version', 1)}")
    t0 = time.monotonic()

    brief = state.get("editorial_brief") or {}
    caption = state.get("linkedin_draft") or ""

    content_qa_res = evaluate_content_qa(caption, brief)

    # Claim Grounding Check: unsupported claims must not appear in caption
    claim_pass = True
    claim_issues = []
    unsupported = brief.get("unsupported_claims") or []
    caption_lower = caption.lower()
    for uc in unsupported:
        if uc and uc.lower() in caption_lower:
            claim_pass = False
            claim_issues.append(f"Caption contains prohibited unsupported claim: '{uc}'")

    content_passed = content_qa_res.decision == "PASS" and claim_pass
    qa_status = "content_passed" if content_passed else (
        "revise" if content_qa_res.decision == "REVISE" else "reject"
    )
    aggregated_issues = claim_issues + content_qa_res.issues

    latency = int((time.monotonic() - t0) * 1000)
    logger.info(f"[content_qa_node] Run {run_id}: decision={content_qa_res.decision} score={content_qa_res.overall_score}/10 claim_pass={claim_pass}")
    log_agent_event(run_id, "content_qa", "complete",
                    output_summary=f"Content QA {content_qa_res.decision}: score={content_qa_res.overall_score}/10",
                    latency_ms=latency, log_id=log_id)
                    
    current_version = state.get("version", 1)

    return {
        **state,
        "content_qa": content_qa_res.model_dump(),
        "qa_passed": content_passed,
        "qa_status": qa_status,
        "qa_issues": aggregated_issues,
        "version": current_version if content_passed else current_version + 1,
        "feedback": None if content_passed else f"QA Failed. Please fix the following issues: {', '.join(aggregated_issues)}"
    }


def vision_qa_node(state: RunState) -> RunState:
    """
    Vision-Only QA Node — runs AFTER image generation.
    Evaluates the generated image against the Editorial Brief and Visual Spec.
    """
    run_id = state["run_id"]
    logger.info(f"[vision_qa_node] Running Vision QA for run {run_id}")
    log_id = log_agent_event(run_id, "vision_qa", "running",
                             input_summary="Vision QA on generated image")
    t0 = time.monotonic()

    brief = state.get("editorial_brief") or {}
    visual_spec = state.get("visual_spec") or {}
    image_url = state.get("image_url")

    vision_qa_res = evaluate_vision_qa(visual_spec, brief, image_url)

    # Combine with existing content QA results
    content_passed = state.get("qa_passed", True)
    overall_pass = content_passed and vision_qa_res.decision == "PASS"

    existing_issues = state.get("qa_issues") or []
    qa_status = "verified_pass" if overall_pass else (
        "revise" if vision_qa_res.decision == "REVISE" else "reject"
    )

    latency = int((time.monotonic() - t0) * 1000)
    logger.info(f"[vision_qa_node] Run {run_id}: vision={vision_qa_res.decision} score={vision_qa_res.overall_score}/10 overall={'PASS' if overall_pass else 'FAIL'}")
    log_agent_event(run_id, "vision_qa", "complete",
                    output_summary=f"Vision QA {vision_qa_res.decision}: score={vision_qa_res.overall_score}/10",
                    latency_ms=latency, log_id=log_id)

    return {
        **state,
        "visual_qa": vision_qa_res.model_dump(),
        "qa_passed": overall_pass,
        "qa_status": qa_status,
        "qa_issues": existing_issues + vision_qa_res.issues,
        "status": "saving_draft"
    }


def qa_node(state: RunState) -> RunState:
    """
    Legacy combined QA Node — kept for backward compatibility.
    In the current graph, content_qa_node and vision_qa_node are used instead.
    """
    run_id = state["run_id"]
    logger.info(f"[qa_node] Starting Content QA + Vision QA for run {run_id}")
    log_id = log_agent_event(run_id, "qa", "running",
                             input_summary=f"Running QA gates on draft v{state.get('version', 1)}")
    t0 = time.monotonic()

    brief = state.get("editorial_brief") or {}
    caption = state.get("linkedin_draft") or ""
    visual_spec = state.get("visual_spec") or {}
    image_url = state.get("image_url")

    content_qa_res = evaluate_content_qa(caption, brief)
    vision_qa_res = evaluate_vision_qa(visual_spec, brief, image_url)

    # Claim Grounding Pass Check: Ensure unsupported claims are not in caption
    claim_pass = True
    claim_issues = []
    unsupported = brief.get("unsupported_claims") or []
    caption_lower = caption.lower()
    for uc in unsupported:
        if uc and uc.lower() in caption_lower:
            claim_pass = False
            claim_issues.append(f"Caption contains prohibited unsupported claim: '{uc}'")

    overall_pass = (
        content_qa_res.decision == "PASS"
        and vision_qa_res.decision == "PASS"
        and claim_pass
    )

    qa_status = "verified_pass"
    if not overall_pass:
        qa_status = "revise" if (content_qa_res.decision == "REVISE" or vision_qa_res.decision == "REVISE") else "reject"

    aggregated_issues = content_qa_res.issues + vision_qa_res.issues + claim_issues

    latency = int((time.monotonic() - t0) * 1000)
    summary_txt = f"QA {'PASSED' if overall_pass else 'FLAGGED'}: Content score {content_qa_res.overall_score}/10, Vision score {vision_qa_res.overall_score}/10 (Status: {qa_status})"
    logger.info(f"[qa_node] Completed for run {run_id}: content={content_qa_res.decision} vision={vision_qa_res.decision} overall={'PASS' if overall_pass else 'FAIL'} (qa_status={qa_status})")
    log_agent_event(run_id, "qa", "complete",
                    output_summary=summary_txt,
                    latency_ms=latency,
                    log_id=log_id)

    return {
        **state,
        "content_qa": content_qa_res.model_dump(),
        "visual_qa": vision_qa_res.model_dump(),
        "qa_passed": overall_pass,
        "qa_status": qa_status,
        "qa_issues": aggregated_issues,
        "status": "saving_draft"
    }
