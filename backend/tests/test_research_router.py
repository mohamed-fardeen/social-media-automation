"""
Tests for Modular Research System — Planner parsing, Source Router deterministic rules,
URL and Content Hash deduplication, provider fallbacks, and concurrency safeguards.
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock

from app.schemas.research_plan import ResearchPlan, SocialSearchTarget, ResearchDocument
from app.services.research.router import SourceRouter, normalize_canonical_url, compute_content_hash
from app.services.research.tavily import TavilyProvider
from app.services.research.firecrawl import FirecrawlProvider
from app.services.research.apify import ApifyProvider


class TestDeduplicationUtilities:
    def test_normalize_canonical_url(self):
        # Scheme + host are normalized to lowercase; path case is preserved (case-sensitive by RFC)
        # UTM and tracking params are stripped; trailing slash removed
        raw_url = "HTTPS://Example.COM/Blog/Post-1/?utm_source=twitter&utm_medium=social&ref=123"
        normalized = normalize_canonical_url(raw_url)
        assert normalized == "https://example.com/Blog/Post-1"

    def test_normalize_url_with_no_tracking_params(self):
        raw_url = "https://example.com/article?page=2"
        normalized = normalize_canonical_url(raw_url)
        assert "utm_" not in normalized
        assert "page=2" in normalized  # Non-tracking param preserved

    def test_compute_content_hash(self):
        text1 = "  This IS a Sample Document Text for Hash Verification.  "
        text2 = "this is a sample document text for hash verification."
        assert compute_content_hash(text1) == compute_content_hash(text2)


class TestDeterministicSourceRouter:
    def test_routing_rules(self):
        router = SourceRouter()
        
        # Test 1: Direct URL target -> Firecrawl (if key available) or Tavily fallback
        with patch.dict(router.available_keys, {"firecrawl": True}):
            assert router.route_task("url", "https://example.com/page") == "firecrawl"
        with patch.dict(router.available_keys, {"firecrawl": False}):
            assert router.route_task("url", "https://example.com/page") == "tavily"

        # Test 2: Social target (Instagram / Reddit / X) -> Apify (if key available) or Tavily site search fallback
        st_ig = SocialSearchTarget(platform="instagram", query_or_handle="tech_trends")
        with patch.dict(router.available_keys, {"apify": True}):
            assert router.route_task("social", st_ig) == "apify"
        with patch.dict(router.available_keys, {"apify": False}):
            assert router.route_task("social", st_ig) == "tavily"

        # Test 3: LinkedIn target -> LinkedIn Official (if key available) or Tavily site search fallback
        st_li = SocialSearchTarget(platform="linkedin", query_or_handle="ai_leaders")
        with patch.dict(router.available_keys, {"linkedin_api": True}):
            assert router.route_task("social", st_li) == "linkedin_official"
        with patch.dict(router.available_keys, {"linkedin_api": False}):
            assert router.route_task("social", st_li) == "tavily"

        # Test 4: General web query -> Tavily
        assert router.route_task("web", "general query") == "tavily"


class TestDeduplicationAndPayloadControl:
    @pytest.mark.asyncio
    async def test_deduplication_by_url_and_content_hash(self):
        router = SourceRouter()

        doc1 = ResearchDocument(id="1", title="Doc 1", url="https://example.com/article?utm_source=a", content="Unique text A", provider="tavily", platform="web")
        doc2 = ResearchDocument(id="2", title="Doc 2 Duplicate URL", url="https://example.com/article?utm_source=b", content="Unique text B", provider="tavily", platform="web")
        doc3 = ResearchDocument(id="3", title="Doc 3 Duplicate Content", url="https://other.com/article", content="Unique text A", provider="firecrawl", platform="web")
        doc4 = ResearchDocument(id="4", title="Doc 4 Unique", url="https://third.com/article", content="Unique text C", provider="apify", platform="instagram")

        plan = ResearchPlan(
            summary_of_intent="Test deduplication",
            web_queries=["test query"]
        )

        with patch.object(router, "_execute_provider_task", return_value=[doc1, doc2, doc3, doc4]):
            results = await router.execute_plan_async(plan)
            # doc2 should be rejected due to canonical URL match with doc1
            # doc3 should be rejected due to content hash match with doc1
            # Only doc1 and doc4 should remain
            urls = [d.url for d in results]
            assert len(results) == 2
            assert doc1.url in urls
            assert doc4.url in urls

    @pytest.mark.asyncio
    async def test_content_truncation_for_large_documents(self):
        router = SourceRouter()
        huge_text = "Word " * 2000  # >1500 chars
        huge_doc = ResearchDocument(id="1", title="Huge Doc", url="https://huge.com/doc", content=huge_text, provider="firecrawl", platform="web")

        plan = ResearchPlan(summary_of_intent="Test payload", web_queries=["test"])
        with patch.object(router, "_execute_provider_task", return_value=[huge_doc]):
            results = await router.execute_plan_async(plan)
            assert len(results) == 1
            assert len(results[0].content) <= 1600
            assert "[truncated]" in results[0].content


class TestProviderFallbacks:
    def test_tavily_provider_fallback(self):
        with patch("app.services.research.tavily.settings") as mock_settings:
            mock_settings.TAVILY_API_KEY = ""
            provider = TavilyProvider()
            results = provider.search("AI trends")
            assert len(results) > 0
            assert results[0].provider == "mock"

    def test_firecrawl_provider_fallback(self):
        with patch("app.services.research.firecrawl.settings") as mock_settings:
            mock_settings.FIRECRAWL_API_KEY = ""
            provider = FirecrawlProvider()
            results = provider.search("https://example.com/deep")
            assert len(results) > 0
            assert results[0].provider == "mock"

    def test_apify_provider_fallback(self):
        with patch("app.services.research.apify.settings") as mock_settings:
            mock_settings.APIFY_API_TOKEN = ""
            mock_settings.APIFY_INSTAGRAM_ACTOR = "apify/instagram-post-scraper"
            mock_settings.APIFY_REDDIT_ACTOR = "apify/reddit-scraper"
            mock_settings.APIFY_TWITTER_ACTOR = "apify/twitter-scraper"
            provider = ApifyProvider()
            results = provider.search("growth", platform="instagram")
            assert len(results) > 0
            assert results[0].provider == "mock"
