"""
Apify Research Provider — Specialized social media scraping for Instagram, Reddit, X (Twitter).
Configurable actor identifiers via environment settings.
"""
import uuid
import httpx
import re
from datetime import timedelta
from typing import List, Dict, Any, Optional
from app.services.research.base import BaseResearchProvider
from app.schemas.research_plan import ResearchDocument
from app.config.settings import settings
from app.config.logging import logger


class ApifyProvider(BaseResearchProvider):
    @property
    def provider_name(self) -> str:
        return "apify"

    def __init__(self):
        raw_token = settings.APIFY_API_TOKEN or ""
        self.api_token = raw_token if not raw_token.startswith("your-") else ""
        self.available = bool(self.api_token)
        self.instagram_actor = settings.APIFY_INSTAGRAM_ACTOR
        self.reddit_actor = settings.APIFY_REDDIT_ACTOR
        self.twitter_actor = settings.APIFY_TWITTER_ACTOR

        if not self.available:
            logger.warning("APIFY_API_TOKEN not set or is placeholder. Apify social scraping will fallback to Tavily/mock.")

    def supports_platform(self, platform: str) -> bool:
        platform_clean = platform.lower()
        if platform_clean == "instagram":
            return bool(self.instagram_actor)
        if platform_clean == "reddit":
            return bool(self.reddit_actor)
        if platform_clean in ("x", "twitter"):
            return bool(self.twitter_actor)
        return False

    def search(self, query: str, max_results: int = 5, platform: str = "instagram", **kwargs) -> List[ResearchDocument]:
        """
        Scrapes social media posts for target platform using configurable Apify actors.
        """
        if not self.available or not query or not query.strip():
            return self._mock_results(query, max_results, platform)

        platform_clean = platform.lower()

        # Pick actor based on platform
        if platform_clean == "instagram":
            actor_id = self.instagram_actor
            hashtags = self._instagram_hashtags(query)
            if not hashtags:
                logger.warning(f"Could not derive valid Instagram hashtags from '{query}'. Returning mock.")
                return self._mock_results(query, max_results, platform_clean)
            run_input = {"hashtags": hashtags, "resultsLimit": max_results}
        elif platform_clean == "reddit":
            actor_id = self.reddit_actor
            run_input = {"searches": [query], "maxItems": max_results}
        elif platform_clean in ("x", "twitter"):
            actor_id = self.twitter_actor
            run_input = {"searchTerms": [query], "maxItems": max_results}
        else:
            logger.warning(f"Unsupported Apify platform '{platform}'. Returning mock.")
            return self._mock_results(query, max_results, platform_clean)

        if not actor_id:
            logger.warning(f"No Apify actor configured for platform '{platform_clean}'. Returning mock.")
            return self._mock_results(query, max_results, platform_clean)

        # 1. Try apify-client SDK
        try:
            from apify_client import ApifyClient
            client = ApifyClient(self.api_token)
            run = client.actor(actor_id).call(
                run_input=run_input,
                wait_duration=timedelta(seconds=45)
            )
            
            results: List[ResearchDocument] = []
            if run and "defaultDatasetId" in run:
                dataset_items = client.dataset(run["defaultDatasetId"]).list_items(limit=max_results).items
                for item in dataset_items:
                    text_content = item.get("caption") or item.get("text") or item.get("body") or str(item)
                    url_str = item.get("url") or item.get("postUrl") or f"https://{platform_clean}.com/p/{uuid.uuid4()[:8]}"
                    doc = ResearchDocument(
                        id=str(uuid.uuid4()),
                        title=f"{platform_clean.capitalize()} post: {query}",
                        url=url_str,
                        content=text_content[:1500],
                        provider="apify",
                        platform=platform_clean,
                        score=0.85,
                        engagement={
                            "likes": item.get("likesCount") or item.get("likes", 0),
                            "comments": item.get("commentsCount") or item.get("comments", 0),
                            "shares": item.get("sharesCount") or item.get("retweets", 0)
                        },
                        metadata={"actor_id": actor_id, "query": query}
                    )
                    results.append(doc)
            if results:
                return results
        except Exception as sdk_err:
            logger.warning(f"Apify SDK run failed for actor '{actor_id}': {sdk_err}. Trying REST fallback.")

        # 2. REST API Fallback
        try:
            url = f"https://api.apify.com/v2/acts/{actor_id.replace('/', '~')}/run-sync-get-dataset-items?token={self.api_token}"
            resp = httpx.post(url, json=run_input, timeout=45)
            if resp.status_code in (200, 201):
                items = resp.json()
                results = []
                for item in items[:max_results]:
                    text_content = item.get("caption") or item.get("text") or item.get("body") or str(item)
                    url_str = item.get("url") or item.get("postUrl") or f"https://{platform_clean}.com/p/{uuid.uuid4()[:8]}"
                    doc = ResearchDocument(
                        id=str(uuid.uuid4()),
                        title=f"{platform_clean.capitalize()} post: {query}",
                        url=url_str,
                        content=text_content[:1500],
                        provider="apify",
                        platform=platform_clean,
                        score=0.85,
                        engagement={
                            "likes": item.get("likesCount") or item.get("likes", 0),
                            "comments": item.get("commentsCount") or item.get("comments", 0)
                        },
                        metadata={"actor_id": actor_id, "query": query}
                    )
                    results.append(doc)
                if results:
                    return results
            else:
                logger.error(f"Apify REST sync run failed ({resp.status_code}): {resp.text[:200]}")
        except Exception as rest_err:
            logger.error(f"Apify REST request exception: {rest_err}")

        return self._mock_results(query, max_results, platform_clean)

    def _instagram_hashtags(self, query: str) -> List[str]:
        stop_words = {
            "and", "the", "for", "with", "from", "into", "latest", "track", "monitor",
            "discover", "identify", "market", "opportunities", "activity", "signals",
            "global", "globally", "india", "in", "social", "media", "content", "strategy",
        }
        clean = re.sub(r"[^A-Za-z0-9# ]+", " ", query or "")
        words = [w.strip("#").lower() for w in clean.split() if w.strip("#")]
        words = [w for w in words if len(w) > 2 and w not in stop_words]
        phrases = []
        if "3d" in words and "printing" in words:
            phrases.append("3dprinting")
        if "construction" in words and "3d" in words:
            phrases.append("construction3dprinting")
        if "concrete" in words and "printing" in words:
            phrases.append("concreteprinting")
        phrases.extend(words[:3])
        deduped = []
        for phrase in phrases:
            tag = re.sub(r"[^A-Za-z0-9_]", "", phrase)
            if tag and tag not in deduped:
                deduped.append(tag)
        return deduped[:3]

    def _mock_results(self, query: str, max_results: int, platform: str) -> List[ResearchDocument]:
        return [
            ResearchDocument(
                id=str(uuid.uuid4()),
                title=f"Trending {platform.capitalize()} topic: {query}",
                url=f"https://{platform}.com/explore/{query.replace(' ', '_')}",
                content=f"Popular social post on {platform.capitalize()} regarding {query}: High user interaction around modern AI automation trends.",
                provider="mock",
                platform=platform,
                score=0.8,
                engagement={"likes": 420, "comments": 35},
                metadata={"mock": True}
            )
        ][:max_results]
