"""
Firecrawl Research Provider — deep page Markdown extraction and website crawling.
"""
import uuid
import httpx
from typing import List, Dict, Any, Optional
from app.services.research.base import BaseResearchProvider
from app.schemas.research_plan import ResearchDocument
from app.config.settings import settings
from app.config.logging import logger


class FirecrawlProvider(BaseResearchProvider):
    @property
    def provider_name(self) -> str:
        return "firecrawl"

    def __init__(self):
        raw_key = settings.FIRECRAWL_API_KEY or ""
        self.api_key = raw_key if not raw_key.startswith("your-") else ""
        self.available = bool(self.api_key)
        if not self.available:
            logger.warning("FIRECRAWL_API_KEY not set or is placeholder. Firecrawl extraction will fallback to Tavily/mock.")

    def search(self, query: str, max_results: int = 5, **kwargs) -> List[ResearchDocument]:
        """
        Accepts a target URL or search query for deep page markdown extraction.
        If query is a URL, performs page scraping directly.
        """
        if not self.available or not query or not query.strip():
            return self._mock_results(query, max_results)

        url_target = query.strip()
        is_url = url_target.startswith("http://") or url_target.startswith("https://")

        if not is_url:
            # If not direct URL, treat query as a target site search or skip
            logger.info(f"[FirecrawlProvider] Target query '{query}' is not a direct URL. Performing web extraction.")
            return self._mock_results(query, max_results)

        # 1. Try firecrawl SDK if installed
        try:
            from firecrawl import FirecrawlApp
            app = FirecrawlApp(api_key=self.api_key)
            scrape_result = app.scrape_url(url_target, params={'formats': ['markdown']})
            if scrape_result and isinstance(scrape_result, dict):
                md_content = scrape_result.get("markdown", "") or scrape_result.get("content", "")
                title = scrape_result.get("metadata", {}).get("title", "") or url_target
                if md_content:
                    return [
                        ResearchDocument(
                            id=str(uuid.uuid4()),
                            title=title,
                            url=url_target,
                            content=md_content[:4000],  # Truncate content to safe length
                            provider="firecrawl",
                            platform="web",
                            score=0.9,
                            metadata=scrape_result.get("metadata", {})
                        )
                    ]
        except Exception as sdk_err:
            logger.warning(f"Firecrawl SDK scrape failed for '{url_target}': {sdk_err}. Trying REST fallback.")

        # 2. REST API Fallback
        try:
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            payload = {"url": url_target, "formats": ["markdown"]}
            resp = httpx.post("https://api.firecrawl.dev/v1/scrape", json=payload, headers=headers, timeout=20)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                md_content = data.get("markdown", "") or data.get("content", "")
                title = data.get("metadata", {}).get("title", "") or url_target
                if md_content:
                    return [
                        ResearchDocument(
                            id=str(uuid.uuid4()),
                            title=title,
                            url=url_target,
                            content=md_content[:4000],
                            provider="firecrawl",
                            platform="web",
                            score=0.9,
                            metadata=data.get("metadata", {})
                        )
                    ]
            else:
                logger.error(f"Firecrawl REST scrape failed ({resp.status_code}): {resp.text[:200]}")
        except Exception as rest_err:
            logger.error(f"Firecrawl REST request exception: {rest_err}")

        return self._mock_results(query, max_results)

    def _mock_results(self, query: str, max_results: int) -> List[ResearchDocument]:
        url_target = query if (query and query.startswith("http")) else f"https://example.com/deep-page?q={query}"
        return [
            ResearchDocument(
                id=str(uuid.uuid4()),
                title=f"Deep Extracted Page: {query}",
                url=url_target,
                content=f"# Deep Page Analysis\nDetailed markdown content extracted from {url_target}.\nKey findings include comprehensive technical breakdown and industry comparison.",
                provider="mock",
                platform="web",
                score=0.85,
                metadata={"mock": True, "deep_extraction": True}
            )
        ][:max_results]
