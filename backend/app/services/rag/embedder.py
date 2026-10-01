import httpx
from typing import List, Optional
from app.config.settings import settings
from app.config.logging import logger

class GeminiEmbeddingProvider:
    """
    Google Gemini Embeddings Provider using gemini-embedding-001 with 768-dimensional vectors.
    Uses the new official `google.genai` SDK with an HTTP REST fallback.
    """

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.EMBEDDING_MODEL or "gemini-embedding-001"
        self.dimension = getattr(settings, "EMBEDDING_DIMENSION", 768)
        self.client = None
        self.available = bool(self.api_key)

        if self.available:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Google GenAI SDK client init warning: {e}. Will rely on HTTP REST fallback.")

    def embed(self, text: str) -> Optional[List[float]]:
        if not self.available or not text or not text.strip():
            return None

        clean_text = text.replace("\n", " ").strip()

        # 1. Try modern google.genai SDK
        if self.client:
            try:
                from google.genai import types
                res = self.client.models.embed_content(
                    model=self.model,
                    contents=clean_text,
                    config=types.EmbedContentConfig(output_dimensionality=self.dimension)
                )
                if res and res.embeddings and len(res.embeddings) > 0:
                    return res.embeddings[0].values
            except Exception as e:
                logger.warning(f"SDK embedding failed for '{clean_text[:30]}...': {e}. Trying REST fallback.")

        # 2. HTTP REST Fallback
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:embedContent?key={self.api_key}"
            payload = {
                "model": f"models/{self.model}",
                "content": {"parts": [{"text": clean_text}]},
                "outputDimensionality": self.dimension
            }
            response = httpx.post(url, json=payload, timeout=20)
            if response.status_code == 200:
                data = response.json()
                return data.get("embedding", {}).get("values", [])
            else:
                logger.error(f"REST Gemini embedding failed ({response.status_code}): {response.text[:200]}")
        except Exception as e:
            logger.error(f"Gemini REST embedding request exception: {e}")

        return None

    def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        if not self.available or not texts:
            return [None] * len(texts)

        clean_texts = [t.replace("\n", " ").strip() for t in texts]

        # 1. Try SDK batch embedding
        if self.client:
            try:
                from google.genai import types
                valid_indices = [i for i, t in enumerate(clean_texts) if t]
                valid_texts = [clean_texts[i] for i in valid_indices]

                if valid_texts:
                    res = self.client.models.embed_content(
                        model=self.model,
                        contents=valid_texts,
                        config=types.EmbedContentConfig(output_dimensionality=self.dimension)
                    )
                    if res and res.embeddings and len(res.embeddings) == len(valid_texts):
                        results: List[Optional[List[float]]] = [None] * len(texts)
                        for idx_in_valid, orig_idx in enumerate(valid_indices):
                            results[orig_idx] = res.embeddings[idx_in_valid].values
                        return results
            except Exception as e:
                logger.warning(f"SDK batch embedding failed: {e}. Trying REST batch fallback.")

        # 2. REST batch fallback
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:batchEmbedContents?key={self.api_key}"
            requests_payload = [
                {
                    "model": f"models/{self.model}",
                    "content": {"parts": [{"text": t if t else " "}]},
                    "outputDimensionality": self.dimension
                }
                for t in clean_texts
            ]
            response = httpx.post(url, json={"requests": requests_payload}, timeout=30)
            if response.status_code == 200:
                data = response.json()
                raw_embeddings = data.get("embeddings", [])
                results = []
                for i, emb_obj in enumerate(raw_embeddings):
                    if clean_texts[i]:
                        results.append(emb_obj.get("values", []))
                    else:
                        results.append(None)
                return results
            else:
                logger.error(f"REST batch Gemini embedding failed ({response.status_code}): {response.text[:200]}")
        except Exception as e:
            logger.error(f"Gemini REST batch embedding exception: {e}")

        # Fallback to single calls if batch fails
        return [self.embed(t) for t in texts]


# Alias for backward compatibility & modular provider selection
EmbeddingProvider = GeminiEmbeddingProvider

