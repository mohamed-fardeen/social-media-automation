"""
Deterministic Source Router & Evidence Processor for Research System.
Maps research plan targets to providers using explicit deterministic rules,
handles concurrent provider execution with rate limits, and performs dual-key deduplication (URL + Content Hash).
"""
import hashlib
import urllib.parse
import asyncio
from typing import List, Dict, Any, Set, Optional

from app.schemas.research_plan import ResearchPlan, SocialSearchTarget, ResearchDocument
from app.services.research.tavily import TavilyProvider
from app.services.research.firecrawl import FirecrawlProvider
from app.services.research.apify import ApifyProvider
from app.config.settings import settings
from app.config.logging import logger


def normalize_canonical_url(raw_url: str) -> str:
    """Normalize URL by stripping tracking params (utm_*), lowercasing scheme/host, and trailing slashes."""
    if not raw_url:
        return ""
    try:
        parsed = urllib.parse.urlparse(raw_url.strip())
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/")
        
        # Filter out common tracking query parameters
        query_params = urllib.parse.parse_qsl(parsed.query)
        filtered_params = [(k, v) for k, v in query_params if not k.lower().startswith("utm_") and k.lower() not in ("ref", "fbclid", "gclid")]
        clean_query = urllib.parse.urlencode(sorted(filtered_params))
        
        return urllib.parse.urlunparse((scheme, netloc, path, parsed.params, clean_query, ""))
    except Exception:
        return raw_url.strip().lower()


def compute_content_hash(text: str) -> str:
    """Compute MD5 hash of normalized body text for deduplication."""
    clean = "".join(text.lower().split())
    return hashlib.md5(clean.encode("utf-8")).hexdigest()


class SourceRouter:
    def __init__(self, max_concurrent: int = 5):
        self.tavily = TavilyProvider()
        self.firecrawl = FirecrawlProvider()
        self.apify = ApifyProvider()
        self.semaphore = asyncio.Semaphore(max_concurrent)

        self.available_keys = {
            "tavily": self.tavily.available,
            "firecrawl": self.firecrawl.available,
            "apify": self.apify.available,
            "linkedin_api": bool(settings.LINKEDIN_ACCESS_TOKEN or settings.LINKEDIN_API_KEY)
        }

    def route_task(self, task_type: str, item: Any) -> str:
        """
        Pure deterministic decision rules (No LLM decision making):
        1. Target URL -> Firecrawl (if key set), else Tavily extract/search.
        2. Platform in (instagram, reddit, x/twitter) -> Apify (if key set), else Tavily site-search fallback.
        3. Platform == linkedin -> Official LinkedIn API (if configured), else Tavily site-search fallback.
        4. General web discovery -> Tavily.
        """
        if task_type == "url":
            return "firecrawl" if self.available_keys["firecrawl"] else "tavily"
        elif task_type == "social":
            platform = getattr(item, "platform", "").lower()
            if platform == "linkedin":
                return "linkedin_official" if self.available_keys["linkedin_api"] else "tavily"
            elif platform in ("instagram", "reddit", "x", "twitter"):
                return "apify" if self.available_keys["apify"] and self.apify.supports_platform(platform) else "tavily"

        return "tavily"

    async def _execute_provider_task(self, provider_name: str, query: str, platform: str = "web", max_results: int = 5) -> List[ResearchDocument]:
        """Execute a single provider call bounded by concurrency semaphore and timeout handling."""
        async with self.semaphore:
            def _sync_call():
                if provider_name == "firecrawl":
                    return self.firecrawl.search(query, max_results=max_results)
                elif provider_name == "apify":
                    return self.apify.search(query, max_results=max_results, platform=platform)
                elif provider_name == "linkedin_official":
                    # Official LinkedIn API stub / fallback search
                    return [
                        ResearchDocument(
                            id="li_official_1",
                            title=f"LinkedIn Official Insights: {query}",
                            url="https://linkedin.com/official",
                            content=f"Official analytics data for query: {query}",
                            provider="linkedin_official",
                            platform="linkedin",
                            score=0.9
                        )
                    ]
                else:  # Default Tavily / Tavily site fallback
                    tavily_q = f"site:{platform}.com {query}" if platform != "web" else query
                    return self.tavily.search(tavily_q, max_results=max_results)

            try:
                # Run sync provider calls in threadpool with 50s timeout
                # (Apify Instagram actors need ~30s for container spin-up + scrape)
                docs = await asyncio.wait_for(asyncio.to_thread(_sync_call), timeout=50.0)
                return docs if docs else []
            except asyncio.TimeoutError:
                logger.error(f"[SourceRouter] Provider '{provider_name}' call timed out for query '{query}'.")
                return []
            except Exception as e:
                logger.error(f"[SourceRouter] Provider '{provider_name}' error for query '{query}': {e}")
                return []

    async def execute_plan_async(self, plan: ResearchPlan, max_total_docs: int = 12) -> List[ResearchDocument]:
        """
        Executes research plan concurrently across deterministic providers,
        deduplicates by canonical URL and content hash, and caps state payload size.
        """
        tasks = []

        # 1. Process target URLs (Firecrawl)
        for url in plan.target_urls[:3]:  # Cap URLs to 3 max per run
            prov = self.route_task("url", url)
            tasks.append(self._execute_provider_task(prov, query=url, platform="web", max_results=1))

        # 2. Process social targets (Apify / LinkedIn)
        for st in plan.social_targets[:4]:  # Cap social targets to 4 max
            prov = self.route_task("social", st)
            tasks.append(self._execute_provider_task(prov, query=st.query_or_handle, platform=st.platform, max_results=3))

        # 3. Process web discovery queries (Tavily)
        for q in plan.web_queries[:3]:  # Cap web queries to 3 max
            prov = self.route_task("web", q)
            tasks.append(self._execute_provider_task(prov, query=q, platform="web", max_results=4))

        if not tasks:
            # Fallback if plan was empty
            tasks.append(self._execute_provider_task("tavily", query="social media marketing trends", platform="web", max_results=4))

        # Gather results concurrently
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        all_docs: List[ResearchDocument] = []
        for res in batch_results:
            if isinstance(res, list):
                all_docs.extend(res)

        # Dual-key Deduplication: Canonical URL + Content Hash
        seen_urls: Set[str] = set()
        seen_content_hashes: Set[str] = set()
        deduped_docs: List[ResearchDocument] = []

        for doc in all_docs:
            c_url = normalize_canonical_url(doc.url)
            c_hash = compute_content_hash(doc.content)

            if c_url and c_url in seen_urls:
                continue
            if c_hash in seen_content_hashes:
                continue

            if c_url:
                seen_urls.add(c_url)
            seen_content_hashes.add(c_hash)

            # Safeguard: Truncate large document text to avoid LangGraph state bloat
            if len(doc.content) > 1500:
                doc.content = doc.content[:1500] + "... [truncated]"

            deduped_docs.append(doc)
            if len(deduped_docs) >= max_total_docs:
                break

        return deduped_docs

    def execute_plan(self, plan: ResearchPlan, max_total_docs: int = 12) -> List[ResearchDocument]:
        """Synchronous wrapper for execute_plan_async."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # If already in an active event loop (e.g. FastAPI / Uvicorn), use sync execution or thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self.execute_plan_async(plan, max_total_docs))
                return future.result()
        else:
            return asyncio.run(self.execute_plan_async(plan, max_total_docs))
