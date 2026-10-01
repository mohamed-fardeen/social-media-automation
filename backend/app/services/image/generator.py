import base64
import io
import uuid
from typing import Optional, Tuple, Dict, Any, List
from app.services.image.base import ImageProvider, StubImageProvider
from app.database.supabase_client import get_supabase_client
from app.config.settings import settings
from app.config.logging import logger


class GeminiImageProvider(ImageProvider):
    """
    Google Gemini Multimodal Image Generation provider.
    Uses Flash / Pro models (gemini-3.1-flash-image, gemini-3-pro-image-preview, gemini-2.5-flash-image).
    Supports multimodal reference image inputs for grounding machine and project physical features.
    """

    def __init__(self, model_name: Optional[str] = None):
        # Prefer dedicated image key or visual key; fall back to general Gemini key.
        self.api_key = settings.GEMINI_IMAGE_API_KEY or settings.GEMINI_VISUAL_API_KEY or settings.GEMINI_API_KEY
        self.model_name = model_name or settings.GEMINI_IMAGE_MODEL or "gemini-3.1-flash-image"
        self.client = None
        self.available = bool(self.api_key)

        if self.available:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(
                    f"[GeminiImageProvider] Google GenAI SDK init failed: {e}. "
                    "Provider marked unavailable."
                )
                self.available = False

    def generate(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        reference_image_bytes: Optional[bytes] = None
    ) -> Optional[bytes]:
        if not self.available or not self.client:
            logger.warning(f"[GeminiImageProvider] {self.model_name} not available — skipping.")
            return None

        try:
            from google.genai import types

            logger.info(f"[GeminiImageProvider] Generating content for model {self.model_name} (ref_image={'YES' if reference_image_bytes else 'NO'})...")

            # 1. Dedicated Imagen 3 support via generate_images if explicitly configured
            if "imagen" in self.model_name.lower():
                try:
                    response = self.client.models.generate_images(
                        model=self.model_name,
                        prompt=prompt[:2000],
                        config=dict(
                            number_of_images=1,
                            output_mime_type="image/jpeg",
                        )
                    )
                    if response and getattr(response, "generated_images", None):
                        for img in response.generated_images:
                            if getattr(img, "image", None) and getattr(img.image, "image_bytes", None):
                                logger.info(
                                    f"[GeminiImageProvider] Image generated successfully using {self.model_name}"
                                )
                                return img.image.image_bytes
                    logger.error(f"[GeminiImageProvider] Imagen API did not return any images: {response}")
                except Exception as img_err:
                    logger.error(f"[GeminiImageProvider] Imagen 3 generate_images failed ({self.model_name}): {img_err}")
                return None

            # 2. Gemini multimodal image models using generate_content with response_modalities=["IMAGE"]
            contents = [prompt[:2000]]
            if reference_image_bytes:
                mime = "image/png" if reference_image_bytes[:8] == b'\x89PNG\r\n\x1a\n' else "image/jpeg"
                contents.append(types.Part.from_bytes(data=reference_image_bytes, mime_type=mime))

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"]
                )
            )

            if not response or not getattr(response, "candidates", None):
                prompt_feedback = getattr(response, "prompt_feedback", None) if response else None
                logger.error(
                    f"[GeminiImageProvider] No candidates returned from {self.model_name}. "
                    f"prompt_feedback={prompt_feedback}"
                )
                return None

            candidate = response.candidates[0]
            finish_reason = getattr(candidate, "finish_reason", None)
            safety_ratings = getattr(candidate, "safety_ratings", None)

            if not getattr(candidate, "content", None) or getattr(candidate.content, "parts", None) is None:
                logger.error(
                    f"[GeminiImageProvider] Empty candidate content/parts from {self.model_name}. "
                    f"finish_reason={finish_reason}, safety_ratings={safety_ratings}"
                )
                return None

            for part in candidate.content.parts:
                if getattr(part, "inline_data", None) and getattr(part.inline_data, "data", None):
                    logger.info(
                        f"[GeminiImageProvider] Image generated successfully using {self.model_name}"
                    )
                    return part.inline_data.data
                elif getattr(part, "text", None):
                    logger.warning(
                        f"[GeminiImageProvider] Candidate returned text instead of image: {part.text[:200]}"
                    )

            logger.error(
                f"[GeminiImageProvider] API did not return any image parts. "
                f"finish_reason={finish_reason}, safety_ratings={safety_ratings}"
            )

        except Exception as e:
            logger.error(f"[GeminiImageProvider] Generation failed ({self.model_name}): {e}")

        return None


class GeminiWebBridgeProvider(ImageProvider):
    """Delegates generation to a locally hosted, authenticated Gemini Web bridge.

    The bridge owns browser authentication. Keeping credentials out of this API
    process makes the provider opt-in and prevents a browser session from being
    copied into application configuration.
    """

    def __init__(self):
        self.bridge_url = (settings.GEMINI_WEB_BRIDGE_URL or "").strip()
        self.token = settings.GEMINI_WEB_BRIDGE_TOKEN
        self.available = self.bridge_url.startswith(("http://", "https://"))

    def generate(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        reference_image_bytes: Optional[bytes] = None,
    ) -> Optional[bytes]:
        if not self.available:
            logger.info("[GeminiWebBridgeProvider] No GEMINI_WEB_BRIDGE_URL configured; skipping.")
            return None

        import httpx

        payload: Dict[str, Any] = {
            "prompt": prompt[:2000],
            "width": width,
            "height": height,
        }
        if reference_image_bytes:
            payload["reference_image_base64"] = base64.b64encode(reference_image_bytes).decode("ascii")

        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        try:
            response = httpx.post(self.bridge_url, json=payload, headers=headers, timeout=120)
            response.raise_for_status()
            if response.headers.get("content-type", "").lower().startswith("image/"):
                return response.content

            image_base64 = (response.json() or {}).get("image_base64")
            if not image_base64:
                logger.warning("[GeminiWebBridgeProvider] Bridge response did not contain image_base64.")
                return None
            if image_base64.startswith("data:"):
                image_base64 = image_base64.split(",", 1)[-1]
            return base64.b64decode(image_base64, validate=True)
        except Exception as exc:
            logger.warning(f"[GeminiWebBridgeProvider] Bridge request failed: {exc}")
            return None


class CloudflareImageProvider(ImageProvider):
    """
    Cloudflare Workers AI text-to-image provider (FLUX.1 [schnell]).
    """

    def __init__(self):
        self.account_id = settings.CF_ACCOUNT_ID
        self.api_token = settings.CF_API_TOKEN
        self.model_name = settings.CF_IMAGE_MODEL
        self.available = bool(self.account_id and self.api_token)

    def generate(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        reference_image_bytes: Optional[bytes] = None
    ) -> Optional[bytes]:
        if not self.available:
            logger.warning("[CloudflareImageProvider] CF keys not configured.")
            return None

        import base64
        import httpx

        url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/ai/run/{self.model_name}"
        payload = {"prompt": prompt[:2000]}
        if "flux" not in self.model_name:
            payload.update({"width": width, "height": height})

        try:
            resp = httpx.post(
                url,
                headers={"Authorization": f"Bearer {self.api_token}"},
                json=payload,
                timeout=120,
            )
            if resp.status_code != 200:
                logger.error(
                    f"[CloudflareImageProvider] Failed [{resp.status_code}]: {resp.text[:500]}"
                )
                return None

            content_type = resp.headers.get("content-type", "")
            if content_type.startswith("image/"):
                logger.info(f"[CloudflareImageProvider] Image generated using {self.model_name}")
                return resp.content

            data = resp.json()
            if not data.get("success", True):
                logger.error(f"[CloudflareImageProvider] API error: {data.get('errors')}")
                return None

            b64 = (data.get("result") or {}).get("image")
            if b64:
                logger.info(f"[CloudflareImageProvider] Image generated using {self.model_name}")
                return base64.b64decode(b64)

            logger.error("[CloudflareImageProvider] No image data in response.")
        except Exception as e:
            logger.error(f"[CloudflareImageProvider] Request failed: {e}")

        return None


class DALLEImageProvider(ImageProvider):
    def __init__(self, model_name: str = "gpt-image-1-mini", quality: str = "medium"):
        self.available = bool(settings.IMAGE_API_KEY or settings.OPENAI_API_KEY)
        self.model_name = model_name
        self.quality = quality
        api_key = settings.IMAGE_API_KEY or settings.OPENAI_API_KEY
        if self.available:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)

    def generate(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        reference_image_bytes: Optional[bytes] = None
    ) -> Optional[bytes]:
        if not self.available:
            return None
        try:
            import httpx
            response = self.client.images.generate(
                model=self.model_name,
                prompt=prompt[:4000],
                size="1024x1024",
                quality=self.quality,
                n=1
            )
            image_url = response.data[0].url
            if image_url:
                img_bytes = httpx.get(image_url, timeout=30).content
                return img_bytes
        except Exception as e:
            logger.error(f"[DALLEImageProvider] Failed: {e}")
        return None


def _get_product_reference_bytes(product_key: Optional[str]) -> Optional[bytes]:
    """Fetch reference image bytes via exact linked_to_name lookup from brand_reference_images."""
    if not product_key:
        return None
    try:
        from app.services.brand_reference_images import get_reference_images_for_name
        import urllib.request

        urls = get_reference_images_for_name(product_key)
        if urls:
            ref_url = urls[0]
            logger.info(f"[ImageGen] Fetching reference image from exact lookup for '{product_key}': {ref_url}")
            req = urllib.request.Request(ref_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
                if data:
                    logger.info(f"[ImageGen] Successfully loaded {len(data)} bytes of reference imagery for '{product_key}'.")
                    return data
    except Exception as e:
        logger.warning(f"[ImageGen] Could not fetch reference image for '{product_key}': {e}")
    return None


def _apply_label_overlays(image_bytes: bytes, overlay_spec: Optional[list]) -> bytes:
    """Applies crisp post-generation text labels as neat semi-transparent badges."""
    if not overlay_spec or not isinstance(overlay_spec, list):
        return image_bytes
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        width, height = img.size

        # Create overlay layer
        overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)

        font_size = max(18, int(height * 0.028))
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            try:
                font = ImageFont.truetype("DejaVuSans.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()

        margin = int(width * 0.04)
        padding_x = int(font_size * 0.7)
        padding_y = int(font_size * 0.4)

        for item in overlay_spec:
            if not isinstance(item, dict):
                continue
            text = (item.get("text") or "").strip()
            pos = (item.get("position") or "top-left").lower().strip()
            if not text:
                continue

            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]

            badge_w = text_w + (padding_x * 2)
            badge_h = text_h + (padding_y * 2)

            if "top-left" in pos:
                box_x0 = margin
                box_y0 = margin
            elif "top-right" in pos:
                box_x0 = width - margin - badge_w
                box_y0 = margin
            elif "bottom-left" in pos:
                box_x0 = margin
                box_y0 = height - margin - badge_h
            elif "bottom-right" in pos:
                box_x0 = width - margin - badge_w
                box_y0 = height - margin - badge_h
            elif "center" in pos:
                box_x0 = (width - badge_w) // 2
                box_y0 = (height - badge_h) // 2
            else:
                box_x0 = margin
                box_y0 = margin

            box_x1 = box_x0 + badge_w
            box_y1 = box_y0 + badge_h

            draw.rounded_rectangle([box_x0, box_y0, box_x1, box_y1], radius=8, fill=(15, 23, 42, 200), outline=(255, 255, 255, 60), width=1)
            draw.text((box_x0 + padding_x, box_y0 + padding_y), text, font=font, fill=(255, 255, 255, 240))

        composited = Image.alpha_composite(img, overlay).convert("RGB")
        out_buf = io.BytesIO()
        composited.save(out_buf, format="JPEG", quality=95)
        logger.info(f"[ImageGen] Successfully applied {len(overlay_spec)} label overlays via PIL.")
        return out_buf.getvalue()
    except Exception as e:
        logger.warning(f"[ImageGen] Label overlay application failed: {e}. Returning raw image.")
        return image_bytes
def check_image_providers_health() -> Dict[str, Any]:
    """Lightweight startup check verifying image generation models without silent 404."""
    health_results = {}
    gemini_key = settings.GEMINI_VISUAL_API_KEY or settings.GEMINI_IMAGE_API_KEY or settings.GEMINI_API_KEY
    if gemini_key:
        try:
            from google import genai
            client = genai.Client(api_key=gemini_key)
            models = [m.name for m in client.models.list()]
            configured_model = settings.GEMINI_IMAGE_MODEL or "gemini-3.1-flash-image"
            full_model_name = f"models/{configured_model}" if not configured_model.startswith("models/") else configured_model
            is_valid = full_model_name in models or configured_model in models
            health_results["gemini"] = {
                "configured_model": configured_model,
                "valid": is_valid
            }
            if not is_valid:
                logger.warning(
                    f"[STARTUP WARNING] Gemini image model '{configured_model}' not found in API model list! "
                    "Image generation will fail over to secondary providers."
                )
        except Exception as e:
            health_results["gemini"] = {"error": str(e), "valid": False}
            logger.warning(f"[STARTUP WARNING] Gemini image provider health check error: {e}")

    if settings.CF_ACCOUNT_ID and settings.CF_API_TOKEN:
        health_results["cloudflare"] = {
            "model": settings.CF_IMAGE_MODEL,
            "configured": True
        }

    return health_results


async def generate_and_store_image(
    prompt: str,
    run_id: str,
    referenced_product: Optional[str] = None,
    label_overlay_spec: Optional[list] = None
) -> Tuple[Optional[str], Optional[str]]:
    """
    Generate an image using the best available provider and store it in Supabase.
    If label_overlay_spec is provided, applies crisp programmatic text badges onto the image.
    Returns a tuple of (public_url, used_provider_name), or (None, None) on failure.
    """
    providers = []

    # 1. Fetch multimodal reference bytes if a specific product is referenced
    ref_bytes = _get_product_reference_bytes(referenced_product)
    
    # Fetch brand profile for settings
    from app.services.brand_profile import get_brand_profile
    profile = get_brand_profile("default") # In the future, this should take run_id or brand_id, but we default to 'default' for now
    
    primary_provider = profile.get("image_primary_provider", "openai")
    openai_model = profile.get("image_openai_model", "gpt-image-1-mini")
    openai_quality = profile.get("image_openai_quality", "medium")

    # Helper function to add Gemini models
    def add_gemini_providers():
        gemini_key = settings.GEMINI_VISUAL_API_KEY or settings.GEMINI_IMAGE_API_KEY or settings.GEMINI_API_KEY
        if gemini_key:
            gemini_models = [
                "gemini-3.1-flash-image",
                "gemini-3-pro-image-preview",
                "gemini-2.5-flash-image",
            ]
            configured = settings.GEMINI_IMAGE_MODEL
            if configured and configured not in gemini_models:
                gemini_models.insert(0, configured)
            elif configured and configured in gemini_models:
                gemini_models.remove(configured)
                gemini_models.insert(0, configured)

            for m_name in gemini_models:
                g_provider = GeminiImageProvider(model_name=m_name)
                if g_provider.available:
                    providers.append(g_provider)
                    
    # Helper function to add OpenAI provider
    def add_openai_provider():
        if settings.IMAGE_API_KEY or settings.OPENAI_API_KEY:
            providers.append(DALLEImageProvider(model_name=openai_model, quality=openai_quality))

    def add_gemini_web_bridge():
        provider = GeminiWebBridgeProvider()
        if provider.available:
            providers.append(provider)

    if primary_provider == "gemini_web":
        add_gemini_web_bridge()
        add_gemini_providers()
        add_openai_provider()
    elif primary_provider == "openai":
        add_openai_provider()
        add_gemini_providers()
    else:
        add_gemini_providers()
        add_openai_provider()

    # 4. Fallback: Cloudflare FLUX
    if settings.CF_ACCOUNT_ID and settings.CF_API_TOKEN:
        providers.append(CloudflareImageProvider())

    # 5. Fallback Stub
    providers.append(StubImageProvider())

    image_bytes = None
    used_provider_name = None

    clean_prompt = (prompt or "").strip()
    if clean_prompt and not any(k in clean_prompt.lower() for k in ["no humans", "no people", "unpopulated"]):
        clean_prompt = f"{clean_prompt}. Pure architectural and robotic scene, strictly no humans, no people, no workers, no faces, unpopulated site."

    for provider in providers:
        if isinstance(provider, GeminiImageProvider):
            provider_name = f"{type(provider).__name__}({provider.model_name})"
        else:
            provider_name = type(provider).__name__

        logger.info(f"[ImageGen] Attempting generation with provider: {provider_name}")
        try:
            if isinstance(provider, (GeminiImageProvider, GeminiWebBridgeProvider)):
                image_bytes = provider.generate(clean_prompt, reference_image_bytes=ref_bytes)
            else:
                image_bytes = provider.generate(clean_prompt)

            if image_bytes:
                logger.info(f"[ImageGen] Successful generation with {provider_name}.")
                used_provider_name = provider_name
                break
        except Exception as e:
            logger.error(f"[ImageGen] Provider {provider_name} raised exception: {e}")

    if not image_bytes or used_provider_name == "StubImageProvider":
        logger.warning("[ImageGen] All available providers failed to yield image bytes.")
        return None, None

    # Apply programmatic label overlays if specified
    if label_overlay_spec:
        image_bytes = _apply_label_overlays(image_bytes, label_overlay_spec)

    supa = get_supabase_client()
    if not supa:
        logger.warning("[ImageGen] No Supabase client — image not stored.")
        return None, used_provider_name

    filename = f"{run_id}/{uuid.uuid4()}.png"
    content_type = "image/png"
    if image_bytes[:3] == b"\xff\xd8\xff":
        filename = f"{run_id}/{uuid.uuid4()}.jpg"
        content_type = "image/jpeg"

    # Direct REST upload (prevents socket errors on Windows inside asyncio)
    public_url = _upload_via_rest(supa, filename, image_bytes, content_type)
    if public_url:
        return public_url, used_provider_name

    # Fallback upload via SDK
    try:
        res = supa.storage.from_("post-media").upload(
            filename,
            image_bytes,
            {"content-type": content_type}
        )
        public_url = supa.storage.from_("post-media").get_public_url(filename)
        logger.info(f"[ImageGen] Stored in Supabase (SDK fallback): {public_url}")
        return public_url, used_provider_name
    except Exception as e:
        logger.error(f"[ImageGen] Failed to upload image to Supabase storage: {e}")
        return None, used_provider_name


def _upload_via_rest(supa, filename: str, image_bytes: bytes, content_type: str) -> Optional[str]:
    """Direct REST POST to Supabase Storage using the synchronous `requests`
    library. Bypasses the supabase-py storage helper, which uses httpx and
    fails on Windows with WinError 10035 when called from inside asyncio."""
    try:
        import requests
        from app.config.settings import settings as _settings

        url = (_settings.SUPABASE_URL or "").rstrip("/")
        key = _settings.SUPABASE_SERVICE_ROLE_KEY or _settings.SUPABASE_ANON_KEY
        if not url or not key:
            return None

        upload_url = f"{url}/storage/v1/object/post-media/{filename}"
        headers = {
            "Authorization": f"Bearer {key}",
            "apikey": key,
            "Content-Type": content_type,
            "x-upsert": "false",
        }
        resp = requests.post(upload_url, headers=headers, data=image_bytes, timeout=60)
        if resp.status_code in (200, 201):
            public_url = f"{url}/storage/v1/object/public/post-media/{filename}"
            logger.info(f"[ImageGen] Stored in Supabase (REST): {public_url}")
            return public_url
        logger.warning(f"[ImageGen] Supabase REST upload failed: {resp.status_code} {resp.text[:200]}")
        return None
    except Exception as e:
        logger.warning(f"[ImageGen] REST upload fallback error: {e}")
        return None
