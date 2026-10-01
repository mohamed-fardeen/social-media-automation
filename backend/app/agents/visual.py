"""
Visual Director Agent — transforms the Editorial Brief into a technical Visual Specification
and grounded image generation prompt.
Ensures strict 3DCP authenticity (horizontal layer beads, tactile mortar texture, believable robotics)
and conditions on real machine references (ATON, ATOM, G.MINI) when relevant.
"""
import json
import re
import time
from typing import Dict, Any, List, Optional
from app.graph.state import RunState
from app.agents.log_helper import log_agent_event
from app.services.llm.gemini import GeminiLLM
from app.services.llm.groq import GroqLLM
from app.services.brand_profile import get_brand_profile
from app.schemas.editorial import VisualSpecification, VisualType
from app.config.logging import logger
import requests


VISUAL_DIRECTOR_SYSTEM_PROMPT = """You are the Creative & Technical Visual Director for Kelvin6k (robotic 3D concrete printing).
Your job is to design a concrete, physical, and authentic VISUAL SPECIFICATION that visually proves the post's core message.

EDITORIAL-FIRST VISUAL DIRECTIVES:
1. WHAT MUST THE VIEWER UNDERSTAND? The visual must immediately communicate the core technical insight or proof in the Editorial Brief.
2. WHAT PHYSICAL DEMONSTRATION PROVES IT? Identify the exact physical object, toolpath, robotic mechanism, mortar cross-section, or finished structure that demonstrates it.
3. SELECT THE APPROPRIATE VISUAL TYPE:
   - real_project_photography: Completed or in-progress real build.
   - machine_photography: Industrial shot focusing on printer hardware (ATON/ATOM/G.MINI).
   - printing_process: Extrusion nozzle actively laying fresh concrete bead on hardened layers.
   - engineering_cutaway: Cross-section revealing internal toolpath / void geometry / infill.
   - technical_diagram: Clean schematic comparison rendered as PURELY VISUAL geometry/silhouette contrast (e.g. two machine forms side by side, differing reach envelopes shown via shape/shading only). Do NOT rely on text labels to convey the comparison — the visual contrast itself must communicate it. Any necessary labels go in `label_overlay_spec`, not the image prompt.
   - architectural_photography: Premium editorial photograph of curved/parametric facade.
   - text_only: Mark when no visual is needed.

3D CONCRETE PRINTING (3DCP) AUTHENTICITY RULES:
- VISIBLE HORIZONTAL LAYER STRIATIONS: Crisp, distinct stacked horizontal extruded concrete bead ridges (layer height ~20-30mm) along wall contours.
- TACTILE MORTAR TEXTURE: Authentic mid-grey or warm sand-grey architectural mortar with fine aggregate grain and a matte, non-glossy surface.
- REALISTIC ROBOTICS: If depicting machinery, show an industrial 6-axis articulated arm (ATON) or polar rotary printer (ATOM) with an extrusion nozzle. Never depict sci-fi humanoid robots.
- STRICT NEGATIVES (CRITICAL):
  * NO HUMANS, NO PEOPLE, NO WORKERS, NO FACES, NO HANDS: Always exclude human figures, operators, construction crew, hands, or faces. The scene must be purely focused on the architectural structure, robotic machinery, mortar bead striations, or site geometry in an unpopulated industrial/architectural environment.
  * NO smooth poured concrete, NO flat painted drywall, NO glossy plastic, NO CGI game-render sheen, NO neon cyberpunk glows, NO sci-fi futuristic cities.
  * NO LEGIBLE TEXT, LABELS, OR CALLOUTS: Never request rendered text, axis labels (X/Y/Z), panel titles, brand names/logos as text, annotation arrows with text, or "vector callouts" inside the generated image itself. Image generation models cannot reliably render legible typography — any such request will produce garbled, unusable pseudo-text. If a comparison or technical_diagram visual_type needs labels, DO NOT put them in `image_prompt`; instead set `requires_post_label_overlay: true` and describe what the labels should say in a separate `label_overlay_spec` field so labels can be added programmatically after generation, not by the image model.
- MACHINE CONDITIONING: Only include a machine if the post is specifically about printing equipment or robotics. Do NOT force a machine into architectural showcase shots.

Return structured JSON matching VisualSpecification:
{
  "subject": "...",
  "visual_type": "printing_process|architectural_photography|engineering_cutaway|technical_diagram|machine_photography|real_project_photography|text_only",
  "core_understanding": "...",
  "physical_demonstration": "...",
  "key_elements_visible": ["..."],
  "elements_not_visible": ["..."],
  "is_3dcp_relevant": true,
  "authenticity_details": ["..."],
  "machine_reference": "aton|atom|gmini|null",
  "image_prompt": "...",
  "aspect_ratio": "1:1",
  "is_text_only": false,
  "requires_post_label_overlay": false,
  "label_overlay_spec": null
}
"""


def visual_node(state: RunState) -> RunState:
    run_id = state["run_id"]
    log_id = log_agent_event(run_id, "visual", "running",
                             input_summary=f"Visual direction for idea index: {state.get('current_idea_index', 1)}")
    t0 = time.monotonic()

    brief: Dict[str, Any] = state.get("editorial_brief") or {}
    topic = brief.get("topic") or state.get("topic") or "3D Concrete Printing"
    core_message = brief.get("core_message") or state.get("angle") or ""
    visual_story = brief.get("visual_story") or state.get("image_hint") or ""
    visual_type = brief.get("visual_type") or "architectural_photography"
    image_mode = state.get("image_mode") or "with_image"

    # Fast check for text-only mode
    if visual_type == "text_only" or image_mode == "text_only" or (image_mode == "mix" and not visual_story):
        latency = int((time.monotonic() - t0) * 1000)
        log_agent_event(run_id, "visual", "complete",
                        output_summary="Visual skipped (text_only specification)",
                        latency_ms=latency,
                        log_id=log_id)
        spec = VisualSpecification(
            subject=topic,
            visual_type="text_only",
            core_understanding="Text-only post",
            physical_demonstration="None required",
            image_prompt="",
            is_text_only=True,
            requires_post_label_overlay=False,
            label_overlay_spec=None
        )
        return {
            **state,
            "visual_spec": spec.model_dump(),
            "visual_prompt": None,
            "image_url": None,
            "status": "generating_image"
        }

    # Detect machine reference
    scan_text = f"{topic} {core_message} {visual_story} {brief.get('kelvin6k_connection', '')}".lower()
    referenced_product = None
    if "aton" in scan_text or "robotic arm" in scan_text or "6-axis" in scan_text:
        referenced_product = "aton"
    elif "atom" in scan_text or "polar" in scan_text:
        referenced_product = "atom"
    elif "gmini" in scan_text or "g.mini" in scan_text:
        referenced_product = "gmini"

    user_prompt = f"""
=== EDITORIAL BRIEF ===
Topic: {topic}
Core Message: {core_message}
Visual Story / Concept: {visual_story}
Visual Type Requested: {visual_type}
Visual Requirements: {brief.get('visual_requirements', [])}
Visual Negatives: {brief.get('visual_negatives', [])}
Referenced Product: {referenced_product or 'none (focus on structure/process)'}

IMPORTANT CONSTRAINT: Never request rendered text, axis labels, titles, or text callouts in `image_prompt`. Put any labels in `label_overlay_spec`.

Create the complete, professional VisualSpecification and detailed literal image_prompt now.
"""

    try:
        llm = GeminiLLM()
        raw = None
        
        # Fetch reference images from Brand Profile
        brand_id = state.get("brand_id") or "default"
        profile = get_brand_profile(brand_id)
        ref_image_urls = profile.get("reference_images") or []
        
        image_bytes_list = []
        if ref_image_urls:
            for url in ref_image_urls[:3]:  # max 3 for token limits
                try:
                    resp = requests.get(url, timeout=5)
                    resp.raise_for_status()
                    image_bytes_list.append(resp.content)
                except Exception as e:
                    logger.warning(f"[visual_node] Failed to download reference image {url}: {e}")

        try:
            if image_bytes_list:
                logger.info(f"[visual_node] Using multimodal_chat with {len(image_bytes_list)} reference images")
                raw = llm.multimodal_chat(
                    system_prompt=VISUAL_DIRECTOR_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    image_bytes_list=image_bytes_list,
                    temperature=0.6,
                )
            else:
                raw = llm.chat(
                    system_prompt=VISUAL_DIRECTOR_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    temperature=0.6,
                )
        except Exception as gemini_err:
            logger.warning(f"[visual_node] Gemini failed ({gemini_err}). Failing over to Groq GPT-OSS...")
            groq_llm = GroqLLM()
            raw = groq_llm.chat(
                system_prompt=VISUAL_DIRECTOR_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.6,
            )

        raw_clean = re.sub(r"```json\s*|\s*```", "", raw).strip()
        parsed = json.loads(raw_clean)

        raw_prompt = str(parsed.get("image_prompt") or visual_story)
        # Sanitize prompt against accidental text requests
        clean_prompt = re.sub(r"\b(LEFT PANEL:|RIGHT PANEL:|vector callouts|axis labels|with text labels)\b", "", raw_prompt, flags=re.IGNORECASE).strip()

        requires_overlay = bool(parsed.get("requires_post_label_overlay", False))
        raw_overlay = parsed.get("label_overlay_spec")
        overlay_spec = None
        if requires_overlay and raw_overlay:
            if isinstance(raw_overlay, list):
                overlay_spec = []
                for item in raw_overlay:
                    if isinstance(item, dict):
                        overlay_spec.append({
                            "text": str(item.get("text", "")),
                            "position": str(item.get("position", "top-left"))
                        })
                    elif isinstance(item, str) and item.strip():
                        overlay_spec.append({"text": item.strip(), "position": "top-left"})
            elif isinstance(raw_overlay, str) and raw_overlay.strip():
                overlay_spec = [{"text": raw_overlay.strip(), "position": "top-left"}]

        spec = VisualSpecification(
            subject=str(parsed.get("subject") or topic),
            visual_type=parsed.get("visual_type") or visual_type or "architectural_photography",
            core_understanding=str(parsed.get("core_understanding") or core_message),
            physical_demonstration=str(parsed.get("physical_demonstration") or visual_story),
            key_elements_visible=parsed.get("key_elements_visible") or ["horizontal layer lines", "mortar texture"],
            elements_not_visible=parsed.get("elements_not_visible") or ["smooth drywall", "neon CGI glows", "text labels"],
            is_3dcp_relevant=bool(parsed.get("is_3dcp_relevant", True)),
            authenticity_details=parsed.get("authenticity_details") or ["stacked horizontal bead lines", "matte mortar"],
            machine_reference=referenced_product or parsed.get("machine_reference"),
            image_prompt=clean_prompt,
            aspect_ratio=str(parsed.get("aspect_ratio") or "1:1"),
            is_text_only=bool(parsed.get("is_text_only", False)),
            requires_post_label_overlay=requires_overlay,
            label_overlay_spec=overlay_spec
        )

        visual_prompt = spec.image_prompt
        # Guarantee 3DCP authenticity reinforcement in prompt
        if spec.is_3dcp_relevant and "extruded" not in visual_prompt.lower() and "layer" not in visual_prompt.lower():
            visual_prompt += " The structure exhibits distinct stacked horizontal extruded concrete bead layer lines with natural matte mortar texture."

        latency = int((time.monotonic() - t0) * 1000)
        log_agent_event(run_id, "visual", "complete",
                        output_summary=f"Visual blueprint ready ({spec.visual_type}, ref: {referenced_product or 'general'})",
                        latency_ms=latency,
                        log_id=log_id)

        return {
            **state,
            "visual_spec": spec.model_dump(),
            "visual_prompt": visual_prompt,
            "referenced_product": referenced_product,
            "status": "generating_image"
        }

    except Exception as e:
        logger.error(f"[visual_node] Failed for run {run_id}: {e}")
        log_agent_event(run_id, "visual", "error", error=str(e), log_id=log_id)

        fallback_prompt = (
            f"Editorial architectural photography of a 3D-printed concrete structure demonstrating {topic}. "
            "The exterior wall displays distinct, crisp horizontal extruded concrete bead lines with natural tactile mortar texture and fine aggregate grain. "
            "Clean natural daylight on an active construction site, sharp focus, authentic engineering detail, 8k resolution."
        )
        spec = VisualSpecification(
            subject=topic,
            visual_type="architectural_photography",
            core_understanding=core_message,
            physical_demonstration="3D printed concrete structure",
            image_prompt=fallback_prompt,
            is_text_only=False,
            requires_post_label_overlay=False,
            label_overlay_spec=None
        )

        return {
            **state,
            "visual_spec": spec.model_dump(),
            "visual_prompt": fallback_prompt,
            "referenced_product": referenced_product,
            "errors": state.get("errors", []) + [f"visual: {e}"]
        }
