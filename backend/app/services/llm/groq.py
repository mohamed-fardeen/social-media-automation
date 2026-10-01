"""
Groq Cloud LLM client — OpenAI-compatible endpoint.
Configured model: openai/gpt-oss-120b (configured via GROQ_MODEL).

Structured output strategy:
  1. Attempt Groq's JSON-mode (response_format={"type":"json_object"}) for a
     tightly-constrained JSON response, then validate with the Pydantic schema.
  2. If that fails for any compatibility reason, fall back to injecting the
     JSON schema into the user prompt and parsing the raw text response.

NOTE: Groq does NOT support the OpenAI beta `client.beta.chat.completions.parse`
endpoint.  We never call that here.
"""
from typing import Optional, List
import json
import re
from openai import OpenAI
from app.config.settings import settings
from app.config.logging import logger
from pydantic import BaseModel


# Models we route between when one hits a rate limit.
FALLBACK_MODELS: List[str] = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.6-27b",
]


class GroqLLM:
    """
    Groq Cloud LLM client (OpenAI-compatible endpoint).
    Provides high-speed inference for GPT-OSS and other open models on Groq.
    Falls back gracefully to xAI/Grok if GROQ_API_KEY is not set.
    """

    def __init__(self):
        if settings.GROQ_API_KEY:
            self.model = settings.GROQ_MODEL          # openai/gpt-oss-120b
            self.client = OpenAI(
                api_key=settings.GROQ_API_KEY,
                base_url=settings.GROQ_BASE_URL       # https://api.groq.com/openai/v1
            )
            self.provider_name = "Groq"
        elif settings.XAI_API_KEY:
            self.model = settings.XAI_MODEL
            self.client = OpenAI(
                api_key=settings.XAI_API_KEY,
                base_url=settings.XAI_BASE_URL
            )
            self.provider_name = "xAI Grok"
        else:
            self.model = settings.GROQ_MODEL
            self.client = None
            self.provider_name = "Mock"

    def _models_to_try(self) -> List[str]:
        """Configured model first, then FALLBACK_MODELS (deduped)."""
        out = [self.model]
        for m in FALLBACK_MODELS:
            if m and m != self.model and m not in out:
                out.append(m)
        return out

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        msg = str(exc).lower()
        return any(s in msg for s in (
            "rate limit", "429", "too many", "503", "502", "504",
            "tpd", "tokens per day", "service unavailable", "timeout",
            "model_not_found", "does not exist", "404",
        ))

    # ── Plain chat ────────────────────────────────────────────────────────────

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Plain chat completion — returns string response. Routes between
        models in FALLBACK_MODELS on rate limit / upstream errors."""
        if not self.client:
            logger.warning(f"[{self.provider_name}] No API key configured. Returning mock response.")
            return "Mock response: API key not set."

        last_err: Optional[Exception] = None
        for model in self._models_to_try():
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                if model != self.model:
                    logger.info(f"[{self.provider_name}] routed to fallback model {model}")
                return response.choices[0].message.content or ""
            except Exception as e:
                last_err = e
                if self._is_retryable(e):
                    logger.warning(f"[{self.provider_name}] {model} hit {e}; trying next fallback")
                    continue
                raise
        raise last_err if last_err else RuntimeError("All fallback models exhausted")

    # ── Structured output ─────────────────────────────────────────────────────

    def structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: type[BaseModel],
        temperature: float = 0.5,
    ) -> Optional[BaseModel]:
        """
        Structured output — returns a validated Pydantic model instance.

        Strategy (Groq-compatible):
          1. Try Groq's JSON mode (response_format={"type": "json_object"}).
             Parse the returned JSON against the Pydantic schema.
          2. On any failure, fall back to schema-in-prompt approach.
        """
        if not self.client:
            logger.warning(f"[{self.provider_name}] No API key configured.")
            return None

        # ── Attempt 1: JSON mode (routes between models on 429/5xx) ─────────
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        json_system = (
            f"{system_prompt}\n\n"
            "IMPORTANT: You MUST respond with ONLY a valid JSON object. "
            "No markdown, no explanation — raw JSON only.\n"
            f"JSON schema to follow:\n{schema_json}"
        )

        last_err: Optional[Exception] = None
        for model in self._models_to_try():
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": json_system},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    max_tokens=4096,
                )
                raw = response.choices[0].message.content or ""
                data = json.loads(raw)
                if model != self.model:
                    logger.info(f"[{self.provider_name}] routed to fallback model {model}")
                return schema(**data)
            except Exception as e:
                last_err = e
                if self._is_retryable(e):
                    logger.warning(f"[{self.provider_name}] JSON-mode {model} hit {e}; trying next fallback")
                    continue
                logger.debug(
                    f"[{self.provider_name}] JSON-mode structured parse failed on {model}: {e}"
                )
                break

        # ── Attempt 2: Schema-in-prompt fallback ─────────────────────────────
        fallback_prompt = (
            f"{user_prompt}\n\n"
            "Return ONLY a valid JSON object matching this exact JSON schema. "
            "Do not include any text before or after the JSON:\n"
            f"```json\n{schema_json}\n```"
        )
        try:
            raw_text = self.chat(system_prompt, fallback_prompt, temperature)
            # Extract JSON from the response (handle possible markdown fences)
            match = re.search(r"```json\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                brace_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
                json_str = brace_match.group() if brace_match else raw_text

            data = json.loads(json_str)
            return schema(**data)
        except Exception as parse_err:
            logger.error(
                f"[{self.provider_name}] Structured JSON fallback also failed: {parse_err}"
            )
            return None


# Backward-compatibility alias — any code still importing GrokLLM continues to work.
GrokLLM = GroqLLM
