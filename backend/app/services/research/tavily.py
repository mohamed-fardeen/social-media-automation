import uuid
from typing import List, Dict, Any, Optional
from app.services.research.base import BaseResearchProvider
from app.schemas.research_plan import ResearchDocument
from app.config.settings import settings
from app.config.logging import logger


class TavilyProvider(BaseResearchProvider):
    @property
    def provider_name(self) -> str:
        return "tavily"

    def __init__(self):
        raw_key = settings.TAVILY_API_KEY or ""
        self.api_key = raw_key if not raw_key.startswith("your-") else ""
        self.available = bool(self.api_key)
        if not self.available:
            logger.warning("TAVILY_API_KEY not set or is placeholder. Tavily search will return mock data.")

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[ResearchDocument]:
        if not self.available or not query or not query.strip():
            return self._mock_results(query, max_results)

        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=self.api_key)
            response = client.search(
                query=query,
                search_depth="advanced",
                max_results=max_results,
                include_answer=True
            )
            results: List[ResearchDocument] = []
            for r in response.get("results", []):
                url_str = r.get("url", "")
                if not url_str:
                    continue
                doc = ResearchDocument(
                    id=str(uuid.uuid4()),
                    title=r.get("title", "") or "Web Discovery Article",
                    url=url_str,
                    content=r.get("content", ""),
                    provider="tavily",
                    platform="web",
                    score=r.get("score", 0.5),
                    metadata={"query": query, "raw_score": r.get("score")}
                )
                results.append(doc)
            return results if results else self._mock_results(query, max_results)
        except Exception as e:
            logger.error(f"Tavily search failed for '{query}': {e}")
            return self._mock_results(query, max_results)

    def _mock_results(self, query: str, max_results: int) -> List[ResearchDocument]:
        """Return placeholder results when Tavily is not configured."""
        clean_q = query if query else "social media automation"
        return [
            ResearchDocument(
                id=str(uuid.uuid4()),
                title=f"Industry trend related to: {clean_q}",
                url=f"https://example.com/trend-1?q={clean_q.replace(' ', '+')}",
                content=f"Key insight about {clean_q}: Businesses are increasingly adopting AI-driven strategies to stay competitive in dynamic markets.",
                provider="mock",
                platform="web",
                score=0.8,
                metadata={"mock": True}
            ),
            ResearchDocument(
                id=str(uuid.uuid4()),
                title=f"Competitor activity: {clean_q}",
                url=f"https://example.com/competitor-1?q={clean_q.replace(' ', '+')}",
                content=f"Leading companies in the {clean_q} space are focusing on personalization and community engagement.",
                provider="mock",
                platform="web",
                score=0.75,
                metadata={"mock": True}
            )
        ][:max_results]

