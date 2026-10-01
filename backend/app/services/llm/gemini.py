"""
Google Gemini LLM client — GenAI SDK endpoint.
Primary model: gemini-2.5-flash (configured via GEMINI_TEXT_MODEL).

Includes automatic retry with exponential backoff on 503 / resource-exhausted errors.
"""
from typing import Optional, List
import json
import re
import time
from google import genai
from google.genai import types
from app.config.settings import settings
from app.config.logging import logger
from pydantic import BaseModel

# 503 / high-demand errors get retried up to this many times
_MAX_RETRIES = 3
_RETRY_DELAYS = [2, 5, 10]  # seconds between attempts

# Model fallback chain — if configured model is unavailable (404) try these in order
_MODEL_FALLBACKS = [
    "gemini-3.6-flash",
    "gemini-1.5-flash",
]


def _is_transient(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(s in msg for s in ("503", "unavailable", "resource exhausted", "429", "quota", "overloaded"))


class GeminiLLM:
    """
    Google Gemini LLM client (GenAI SDK compatible).
    Provides high-speed inference for gemini-2.5-flash and other Gemini models.
    Retries automatically on 503 / resource-exhausted errors.
    """

    def __init__(self):
        # Prefer the dedicated text key; fall back to the general Gemini key.
        self.api_key = settings.GEMINI_TEXT_API_KEY or settings.GEMINI_API_KEY
        self.model = settings.GEMINI_TEXT_MODEL or "gemini-3.6-flash"
        self.pro_model = "gemini-2.5-pro"  # High-tier model
        self._model_queue = [self.model] + [m for m in _MODEL_FALLBACKS if m != self.model]
        self.client = None
        self.provider_name = "Gemini"

        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(
                    f"[{self.provider_name}] Google GenAI SDK init failed: {e}. "
                    "Provider marked unavailable."
                )
        else:
            self.provider_name = "Mock"

    def _route_model(self, user_prompt: str) -> str:
        """Intelligent model router based on task complexity."""
        complexity_keywords = ["reasoning", "strategy", "copywriter", "editorial brief", "visualspecification"]
        is_complex = len(user_prompt) > 2000 or any(k in user_prompt.lower() for k in complexity_keywords)
        if is_complex:
            logger.info(f"[{self.provider_name}] Routing to PRO model for complex task.")
            return self.pro_model
        return self.model

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Plain chat completion — returns string response. Retries on 503, falls back model on 404."""
        if not self.client:
            logger.warning(f"[{self.provider_name}] No API key configured. Returning mock response.")
            return "Mock response: Gemini API key not set."

        routed_model = self._route_model(user_prompt)
        current_queue = [routed_model] + [m for m in self._model_queue if m != routed_model]

        last_err: Optional[Exception] = None
        for model in current_queue:
            for attempt in range(_MAX_RETRIES):
                try:
                    response = self.client.models.generate_content(
                        model=model,
                        contents=user_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            temperature=temperature,
                            max_output_tokens=max_tokens,
                        )
                    )
                    if model != self.model:
                        logger.info(f"[{self.provider_name}] fell back to model {model}")
                    return response.text or ""
                except Exception as e:
                    last_err = e
                    msg = str(e).lower()
                    if _is_transient(e) and attempt < _MAX_RETRIES - 1:
                        delay = _RETRY_DELAYS[attempt]
                        logger.warning(
                            f"[{self.provider_name}] Transient error (model={model}, attempt={attempt + 1}): {e}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                        continue
                    if "404" in msg or "not_found" in msg or "no longer available" in msg:
                        logger.warning(f"[{self.provider_name}] Model {model} not available (404); trying next.")
                        break  # try next model
                    logger.error(f"[{self.provider_name}] Generation failed: {e}")
                    raise
        raise last_err or RuntimeError("All Gemini models exhausted")

    def multimodal_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        image_bytes_list: List[bytes],
        temperature: float = 0.6,
        max_tokens: int = 4096,
    ) -> str:
        """Chat completion with image bytes (multimodal)."""
        if not self.client:
            return "Mock response"

        routed_model = self._route_model(user_prompt)
        current_queue = [routed_model] + [m for m in self._model_queue if m != routed_model]

        contents = []
        for img_bytes in image_bytes_list:
            contents.append(
                types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
            )
        contents.append(user_prompt)

        last_err: Optional[Exception] = None
        for model in current_queue:
            for attempt in range(_MAX_RETRIES):
                try:
                    response = self.client.models.generate_content(
                        model=model,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            temperature=temperature,
                            max_output_tokens=max_tokens,
                        )
                    )
                    return response.text or ""
                except Exception as e:
                    last_err = e
                    msg = str(e).lower()
                    if _is_transient(e) and attempt < _MAX_RETRIES - 1:
                        time.sleep(_RETRY_DELAYS[attempt])
                        continue
                    if "404" in msg or "not_found" in msg or "no longer available" in msg:
                        break
                    raise
        raise last_err or RuntimeError("All Gemini models exhausted")

    def structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: type[BaseModel],
        temperature: float = 0.5,
    ) -> Optional[BaseModel]:
        """
        Structured output — returns a validated Pydantic model instance.
        Retries on 503 / resource-exhausted errors, falls back model on 404.
        """
        if not self.client:
            logger.warning(f"[{self.provider_name}] No API key configured.")
            try:
                return schema()
            except Exception:
                return None

        routed_model = self._route_model(user_prompt)
        current_queue = [routed_model] + [m for m in self._model_queue if m != routed_model]

        last_err: Optional[Exception] = None
        for model in current_queue:
            for attempt in range(_MAX_RETRIES):
                try:
                    response = self.client.models.generate_content(
                        model=model,
                        contents=user_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            temperature=temperature,
                            response_mime_type="application/json",
                            response_schema=schema,
                        )
                    )
                    raw = response.text or ""
                    if raw.startswith("```"):
                        raw = re.sub(r"^```json\s*", "", raw)
                        raw = re.sub(r"\s*```$", "", raw)
                    if model != self.model:
                        logger.info(f"[{self.provider_name}] structured fell back to model {model}")
                    return schema.model_validate_json(raw)
                except Exception as e:
                    last_err = e
                    msg = str(e).lower()
                    if _is_transient(e) and attempt < _MAX_RETRIES - 1:
                        delay = _RETRY_DELAYS[attempt]
                        logger.warning(
                            f"[{self.provider_name}] Structured transient error (model={model}, attempt={attempt + 1}): {e}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                        continue
                    if "404" in msg or "not_found" in msg or "no longer available" in msg:
                        logger.warning(f"[{self.provider_name}] Structured: model {model} not available (404); trying next.")
                        break  # try next model
                    logger.error(f"[{self.provider_name}] Structured generation failed: {e}")
                    return None
        logger.error(f"[{self.provider_name}] Structured generation exhausted all models: {last_err}")
        return None
