"""
Real Integration Tests for Research System.
Tests all 10 cases: Tavily, Firecrawl, Apify (Instagram/Reddit/X),
missing-key fallbacks, parallel execution, deduplication, and error handling.

Run from backend/ with:
    python -m pytest tests/integration/test_research_integration.py -v -s

Or standalone:
    python tests/integration/test_research_integration.py
"""
import asyncio
import os
import sys
import time
import textwrap
import hashlib
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path

# Ensure backend root is on path when run standalone
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from app.schemas.research_plan import ResearchPlan, SocialSearchTarget, ResearchDocument
from app.services.research.router import SourceRouter, normalize_canonical_url, compute_content_hash
from app.services.research.tavily import TavilyProvider
from app.services.research.firecrawl import FirecrawlProvider
from app.services.research.apify import ApifyProvider
from app.config.settings import settings


# ──────────────────────────────────────────────────────────────────────────────
# Report helpers
# ──────────────────────────────────────────────────────────────────────────────

PASS  = "PASS"
FAIL  = "FAIL"
WARN  = "WARN"
SKIP  = "SKIP"


@dataclass
class CaseResult:
    case_id: int
    title: str
    status: str = PASS
    provider_selected: str = ""
    api_actor_called: str = ""
    result_count: int = 0
    content_extracted: bool = False
    latency_s: float = 0.0
    errors: List[str] = field(default_factory=list)
    fallback_used: bool = False
    sample_doc: Optional[ResearchDocument] = None
    notes: str = ""


def _fmt_doc(doc: ResearchDocument) -> str:
    safe_content = doc.content.encode("ascii", errors="replace").decode("ascii")
    safe_title = doc.title.encode("ascii", errors="replace").decode("ascii")
    safe_url = doc.url.encode("ascii", errors="replace").decode("ascii")
    snippet = textwrap.shorten(safe_content, width=120, placeholder="...")
    return (
        f"    title    : {safe_title[:80]}\n"
        f"    url      : {safe_url[:80]}\n"
        f"    provider : {doc.provider} | platform: {doc.platform}\n"
        f"    score    : {doc.score:.2f}\n"
        f"    content  : {snippet}\n"
    )


def _icon(status: str) -> str:
    return {"PASS": "[PASS]", "WARN": "[WARN]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}.get(status, status)


def _print_case(r: CaseResult):
    print(f"\n{'='*72}")
    print(f"  Case {r.case_id:02d}: {r.title}")
    print(f"  Status         : {_icon(r.status)}")
    print(f"  Provider       : {r.provider_selected}")
    print(f"  API/Actor      : {r.api_actor_called}")
    print(f"  Results        : {r.result_count}")
    print(f"  Content OK     : {'yes' if r.content_extracted else 'no'}")
    print(f"  Latency        : {r.latency_s:.2f}s")
    print(f"  Fallback used  : {'yes' if r.fallback_used else 'no'}")
    for e in r.errors:
        print(f"  Error          : {e}")
    if r.notes:
        print(f"  Notes          : {r.notes}")
    if r.sample_doc:
        print(f"  Sample doc:\n{_fmt_doc(r.sample_doc)}")


# ──────────────────────────────────────────────────────────────────────────────
# Credential detection
# ──────────────────────────────────────────────────────────────────────────────

def _is_real_key(val: Optional[str]) -> bool:
    """True only when value exists and is not a 'your-' placeholder."""
    return bool(val) and not val.startswith("your-")


CREDS = {
    "tavily":    _is_real_key(settings.TAVILY_API_KEY),
    "apify":     _is_real_key(settings.APIFY_API_TOKEN),
    "firecrawl": _is_real_key(settings.FIRECRAWL_API_KEY),
    "linkedin":  _is_real_key(getattr(settings, "LINKEDIN_ACCESS_TOKEN", None))
               or _is_real_key(getattr(settings, "LINKEDIN_API_KEY", None)),
}


# ──────────────────────────────────────────────────────────────────────────────
# Test cases
# ──────────────────────────────────────────────────────────────────────────────

def case_01_tavily_general_web() -> CaseResult:
    """Case 1: General web research -> Tavily"""
    r = CaseResult(1, "General web research -> Tavily")
    prov = TavilyProvider()
    r.provider_selected = "TavilyProvider"
    r.api_actor_called = "TavilyClient.search(search_depth=advanced)"

    t0 = time.perf_counter()
    docs = prov.search("AI content marketing trends 2025", max_results=3)
    r.latency_s = time.perf_counter() - t0

    r.result_count = len(docs)
    r.content_extracted = any(len(d.content) > 30 for d in docs)

    if not CREDS["tavily"]:
        r.fallback_used = True
        r.status = WARN
        r.notes = "TAVILY_API_KEY not configured — mock results returned"
    else:
        real_docs = [d for d in docs if d.provider == "tavily"]
        if not real_docs:
            r.status = WARN
            r.notes = "Tavily key set but returned mock/no results (possibly rate-limited or invalid key)"
        else:
            r.notes = f"Live Tavily results | {len(real_docs)} docs"

    if docs:
        r.sample_doc = docs[0]
    return r


def case_02_firecrawl_specific_url() -> CaseResult:
    """Case 2: Specific URL -> Firecrawl (Tavily fallback if no key)"""
    r = CaseResult(2, "Specific URL -> Firecrawl extraction")
    router = SourceRouter()
    target_url = "https://www.bbc.com/news"
    r.provider_selected = router.route_task("url", target_url)
    r.fallback_used = not CREDS["firecrawl"]
    r.api_actor_called = (
        "FirecrawlApp.scrape_url() / REST POST /v1/scrape"
        if CREDS["firecrawl"]
        else "TavilyClient.search() [Firecrawl not configured]"
    )

    plan = ResearchPlan(
        summary_of_intent="Deep extract BBC News homepage",
        target_urls=[target_url]
    )
    t0 = time.perf_counter()
    docs = router.execute_plan(plan, max_total_docs=5)
    r.latency_s = time.perf_counter() - t0

    r.result_count = len(docs)
    r.content_extracted = any(len(d.content) > 30 for d in docs)

    if not CREDS["firecrawl"]:
        r.status = WARN
        r.notes = "FIRECRAWL_API_KEY not configured — routed to Tavily/mock"
    elif not r.content_extracted:
        r.status = WARN
        r.notes = "Firecrawl key set but returned no content (possibly invalid url or key)"

    if docs:
        r.sample_doc = docs[0]
    return r


def case_03_apify_instagram() -> CaseResult:
    """Case 3: Instagram research -> Apify"""
    r = CaseResult(3, "Instagram research -> Apify")
    prov = ApifyProvider()
    r.provider_selected = "ApifyProvider"
    r.api_actor_called = f"Actor: {prov.instagram_actor}"
    r.fallback_used = not CREDS["apify"]

    t0 = time.perf_counter()
    docs = prov.search("AI marketing", max_results=3, platform="instagram")
    r.latency_s = time.perf_counter() - t0

    r.result_count = len(docs)
    r.content_extracted = any(len(d.content) > 20 for d in docs)

    if not CREDS["apify"]:
        r.fallback_used = True
        r.status = WARN
        r.notes = f"APIFY_API_TOKEN not configured — mock. Actor would be: {prov.instagram_actor}"
    else:
        real_docs = [d for d in docs if d.provider == "apify"]
        if not real_docs:
            r.status = WARN
            r.notes = "Apify key set but returned mock results (possibly actor input validation failed or invalid token)"

    if docs:
        r.sample_doc = docs[0]
    return r


def case_04_apify_reddit() -> CaseResult:
    """Case 4: Reddit research -> Apify"""
    r = CaseResult(4, "Reddit research -> Apify")
    prov = ApifyProvider()
    r.provider_selected = "ApifyProvider"
    r.api_actor_called = f"Actor: {prov.reddit_actor}"
    r.fallback_used = not CREDS["apify"]

    t0 = time.perf_counter()
    docs = prov.search("AI social media strategy", max_results=3, platform="reddit")
    r.latency_s = time.perf_counter() - t0

    r.result_count = len(docs)
    r.content_extracted = any(len(d.content) > 20 for d in docs)

    if not CREDS["apify"]:
        r.fallback_used = True
        r.status = WARN
        r.notes = f"APIFY_API_TOKEN not configured — mock. Actor would be: {prov.reddit_actor}"
    else:
        real_docs = [d for d in docs if d.provider == "apify"]
        if not real_docs:
            r.status = WARN
            r.notes = "Apify key set but returned mock results (possibly actor not found or invalid token)"

    if docs:
        r.sample_doc = docs[0]
    return r


def case_05_apify_twitter_x() -> CaseResult:
    """Case 5: X/Twitter research -> Apify"""
    r = CaseResult(5, "X/Twitter research -> Apify")
    prov = ApifyProvider()
    r.provider_selected = "ApifyProvider"
    r.api_actor_called = f"Actor: {prov.twitter_actor}"
    r.fallback_used = not CREDS["apify"]

    t0 = time.perf_counter()
    docs = prov.search("content marketing 2025", max_results=3, platform="x")
    r.latency_s = time.perf_counter() - t0

    r.result_count = len(docs)
    r.content_extracted = any(len(d.content) > 20 for d in docs)

    if not CREDS["apify"]:
        r.fallback_used = True
        r.status = WARN
        r.notes = f"APIFY_API_TOKEN not configured — mock. Actor would be: {prov.twitter_actor}"
    else:
        real_docs = [d for d in docs if d.provider == "apify"]
        if not real_docs:
            r.status = WARN
            r.notes = "Apify key set but returned mock results (possibly actor not found or invalid token)"

    if docs:
        r.sample_doc = docs[0]
    return r


def case_06_missing_apify_key_fallback() -> CaseResult:
    """Case 6: Missing Apify key -> Tavily site-search fallback"""
    r = CaseResult(6, "Missing Apify key -> Tavily fallback")

    original_token = settings.APIFY_API_TOKEN
    settings.APIFY_API_TOKEN = ""

    router = SourceRouter()
    social_item = SocialSearchTarget(platform="instagram", query_or_handle="AI leadership")
    r.provider_selected = router.route_task("social", social_item)
    r.api_actor_called = "TavilyClient.search('site:instagram.com ...')" if CREDS["tavily"] else "Tavily mock"
    r.fallback_used = True

    plan = ResearchPlan(
        summary_of_intent="Fallback test: Instagram without Apify key",
        social_targets=[social_item]
    )
    t0 = time.perf_counter()
    docs = router.execute_plan(plan, max_total_docs=5)
    r.latency_s = time.perf_counter() - t0

    settings.APIFY_API_TOKEN = original_token

    r.result_count = len(docs)
    r.content_extracted = any(len(d.content) > 20 for d in docs)

    if r.provider_selected != "tavily":
        r.status = FAIL
        r.errors.append(f"Router should have selected 'tavily' but got '{r.provider_selected}'")
    else:
        r.notes = "Router correctly selected Tavily when Apify key is absent"

    if docs:
        r.sample_doc = docs[0]
    return r


def case_07_missing_firecrawl_key_fallback() -> CaseResult:
    """Case 7: Missing Firecrawl key -> Tavily fallback"""
    r = CaseResult(7, "Missing Firecrawl key -> Tavily fallback")

    original_key = settings.FIRECRAWL_API_KEY
    settings.FIRECRAWL_API_KEY = ""

    router = SourceRouter()
    target_url = "https://techcrunch.com"
    r.provider_selected = router.route_task("url", target_url)
    r.api_actor_called = "TavilyClient.search()" if CREDS["tavily"] else "Tavily mock"
    r.fallback_used = True

    plan = ResearchPlan(
        summary_of_intent="Fallback test: URL without Firecrawl key",
        target_urls=[target_url]
    )
    t0 = time.perf_counter()
    docs = router.execute_plan(plan, max_total_docs=5)
    r.latency_s = time.perf_counter() - t0

    settings.FIRECRAWL_API_KEY = original_key

    r.result_count = len(docs)
    r.content_extracted = any(len(d.content) > 20 for d in docs)

    if r.provider_selected != "tavily":
        r.status = FAIL
        r.errors.append(f"Router should have selected 'tavily' but got '{r.provider_selected}'")
    else:
        r.notes = "Router correctly selected Tavily when Firecrawl key is absent"

    if docs:
        r.sample_doc = docs[0]
    return r


def case_08_parallel_multi_provider() -> CaseResult:
    """Case 8: Multi-provider plan -> parallel execution"""
    r = CaseResult(8, "Multi-provider parallel execution")
    router = SourceRouter()
    r.provider_selected = "SourceRouter (parallel: Tavily + Firecrawl/fallback + Apify/fallback)"
    r.api_actor_called = "execute_plan_async() -> asyncio.gather()"

    plan = ResearchPlan(
        summary_of_intent="Multi-provider parallel test",
        web_queries=[
            "AI in B2B marketing 2025",
            "social media automation tools"
        ],
        target_urls=["https://www.marketingweek.com"],
        social_targets=[
            SocialSearchTarget(platform="instagram", query_or_handle="marketing automation", target_type="search"),
        ]
    )

    t0 = time.perf_counter()
    docs = router.execute_plan(plan, max_total_docs=12)
    r.latency_s = time.perf_counter() - t0

    r.result_count = len(docs)
    r.content_extracted = any(len(d.content) > 30 for d in docs)
    providers_seen = sorted({d.provider for d in docs})
    r.notes = f"Providers in output: {providers_seen} | {r.result_count} docs in {r.latency_s:.2f}s"

    if r.result_count == 0:
        r.status = FAIL
        r.errors.append("No results returned from parallel execution")
    elif r.latency_s > 40:
        r.status = WARN
        r.errors.append(f"Parallel execution took {r.latency_s:.1f}s — exceeds 40s budget")

    if docs:
        r.sample_doc = docs[0]
    return r


def case_09_deduplication() -> CaseResult:
    """Case 9: Duplicate URLs and identical content → deduplication"""
    r = CaseResult(9, "Deduplication (URL + content hash)")
    r.provider_selected = "SourceRouter dedup logic"
    r.api_actor_called = "normalize_canonical_url() + compute_content_hash()"

    router = SourceRouter()
    plan = ResearchPlan(
        summary_of_intent="Deduplication test — same query twice",
        web_queries=[
            "AI marketing trends 2025",
            "AI marketing trends 2025",  # exact duplicate
        ]
    )

    t0 = time.perf_counter()
    docs = router.execute_plan(plan, max_total_docs=20)
    r.latency_s = time.perf_counter() - t0

    r.result_count = len(docs)
    r.content_extracted = any(len(d.content) > 20 for d in docs)

    urls = [normalize_canonical_url(d.url) for d in docs]
    hashes = [compute_content_hash(d.content) for d in docs]
    url_dupes = len(urls) - len(set(urls))
    hash_dupes = len(hashes) - len(set(hashes))

    if url_dupes > 0 or hash_dupes > 0:
        r.status = FAIL
        r.errors.append(f"Deduplication failed: {url_dupes} URL dupes, {hash_dupes} content-hash dupes")

    # Validate URL normalizer directly
    url_a = "https://Example.COM/blog/post?utm_source=twitter&utm_medium=cpc"
    url_b = "https://example.com/blog/post?utm_campaign=summer"
    norm_a = normalize_canonical_url(url_a)
    norm_b = normalize_canonical_url(url_b)
    if norm_a != norm_b:
        r.status = FAIL
        r.errors.append(f"URL normalizer mismatch: '{norm_a}' != '{norm_b}'")

    # Validate content hash case/whitespace normalization
    if compute_content_hash("  This IS duplicate.  ") != compute_content_hash("this is duplicate."):
        r.status = FAIL
        r.errors.append("Content hash failed on whitespace/case normalization")

    if r.status == PASS:
        r.notes = f"0 URL dupes, 0 hash dupes | {r.result_count} unique docs | URL normalizer OK | hash normalizer OK"

    if docs:
        r.sample_doc = docs[0]
    return r


def case_10_provider_failure_graceful() -> CaseResult:
    """Case 10: Provider raises exception -> graceful handling, no crash"""
    r = CaseResult(10, "Provider failure -> graceful handling")
    r.provider_selected = "SourceRouter"
    r.api_actor_called = "execute_plan() with Tavily.search() forced to raise RuntimeError"

    import unittest.mock as mock

    router = SourceRouter()
    router.tavily.search = mock.MagicMock(side_effect=RuntimeError("Simulated Tavily API failure"))

    plan = ResearchPlan(
        summary_of_intent="Failure resilience test",
        web_queries=["test query for failure handling"]
    )

    t0 = time.perf_counter()
    try:
        docs = router.execute_plan(plan, max_total_docs=5)
        r.latency_s = time.perf_counter() - t0
        r.result_count = len(docs)
        r.content_extracted = any(len(d.content) > 10 for d in docs)
        r.notes = f"Handled gracefully -- returned {r.result_count} docs (0 expected), no exception raised"
        if docs:
            r.sample_doc = docs[0]
    except Exception as e:
        r.latency_s = time.perf_counter() - t0
        r.status = FAIL
        r.errors.append(f"Uncaught exception from SourceRouter: {type(e).__name__}: {e}")

    return r


# ──────────────────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────────────────

def _print_credential_summary():
    print(f"\n{'='*72}")
    print(f"  CREDENTIAL STATUS")
    print(f"{'='*72}")
    for name, ok in CREDS.items():
        status = "CONFIGURED" if ok else "MISSING / PLACEHOLDER"
        print(f"  {name:<20} {status}")
    print()


def _print_final_summary(results: List[CaseResult]):
    print(f"\n{'='*72}")
    print("  INTEGRATION TEST SUMMARY")
    print(f"{'='*72}")
    pass_n  = sum(1 for r in results if r.status == PASS)
    warn_n  = sum(1 for r in results if r.status == WARN)
    fail_n  = sum(1 for r in results if r.status == FAIL)
    skip_n  = sum(1 for r in results if r.status == SKIP)
    total_t = sum(r.latency_s for r in results)

    for r in results:
        icons = {"PASS": "[+]", "WARN": "[~]", "FAIL": "[!]", "SKIP": "[-]"}
        icon = icons.get(r.status, "?")
        print(f"  {icon} Case {r.case_id:02d}: {r.title:<48} {r.latency_s:.2f}s")

    print(f"\n  Total: {pass_n} pass, {warn_n} warn, {fail_n} fail, {skip_n} skip  |  {total_t:.2f}s wall-clock")

    print("\n  PROVIDER LIVE STATUS")
    print(f"  Tavily    : {'LIVE' if CREDS['tavily'] else 'MOCK  (TAVILY_API_KEY is placeholder)'}")
    print(f"  Firecrawl : {'LIVE' if CREDS['firecrawl'] else 'MOCK  (FIRECRAWL_API_KEY is placeholder)'}")
    print(f"  Apify     : {'LIVE' if CREDS['apify'] else 'MOCK  (APIFY_API_TOKEN is placeholder)'}")
    print(f"  LinkedIn  : {'CONFIGURED' if CREDS['linkedin'] else 'NOT CONFIGURED'}")

    if fail_n > 0:
        print(f"\n  FAIL: {fail_n} test(s) FAILED -- see errors above.")
    else:
        print("\n  OK: All cases passed or warned cleanly -- no unhandled exceptions or crashes.")


# ──────────────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────────────

ALL_CASES = [
    case_01_tavily_general_web,
    case_02_firecrawl_specific_url,
    case_03_apify_instagram,
    case_04_apify_reddit,
    case_05_apify_twitter_x,
    case_06_missing_apify_key_fallback,
    case_07_missing_firecrawl_key_fallback,
    case_08_parallel_multi_provider,
    case_09_deduplication,
    case_10_provider_failure_graceful,
]


def run_all():
    print(f"\n{'='*72}")
    print("  RESEARCH SYSTEM — REAL INTEGRATION TESTS")
    print(f"{'='*72}")
    _print_credential_summary()

    results = []
    for fn in ALL_CASES:
        try:
            result = fn()
        except Exception as e:
            result = CaseResult(
                case_id=0,
                title=fn.__name__,
                status=FAIL,
                errors=[f"Test runner exception: {type(e).__name__}: {e}"]
            )
        _print_case(result)
        results.append(result)

    _print_final_summary(results)
    return results


# ── pytest compatibility ──────────────────────────────────────────────────────

def test_case_01_tavily():
    r = case_01_tavily_general_web(); _print_case(r)
    assert r.status in (PASS, WARN), f"Case 01 FAILED: {r.errors}"

def test_case_02_firecrawl():
    r = case_02_firecrawl_specific_url(); _print_case(r)
    assert r.status in (PASS, WARN), f"Case 02 FAILED: {r.errors}"

def test_case_03_apify_instagram():
    r = case_03_apify_instagram(); _print_case(r)
    assert r.status in (PASS, WARN), f"Case 03 FAILED: {r.errors}"

def test_case_04_apify_reddit():
    r = case_04_apify_reddit(); _print_case(r)
    assert r.status in (PASS, WARN), f"Case 04 FAILED: {r.errors}"

def test_case_05_apify_twitter():
    r = case_05_apify_twitter_x(); _print_case(r)
    assert r.status in (PASS, WARN), f"Case 05 FAILED: {r.errors}"

def test_case_06_missing_apify_fallback():
    r = case_06_missing_apify_key_fallback(); _print_case(r)
    assert r.status in (PASS, WARN), f"Case 06 FAILED: {r.errors}"

def test_case_07_missing_firecrawl_fallback():
    r = case_07_missing_firecrawl_key_fallback(); _print_case(r)
    assert r.status in (PASS, WARN), f"Case 07 FAILED: {r.errors}"

def test_case_08_parallel():
    r = case_08_parallel_multi_provider(); _print_case(r)
    assert r.status in (PASS, WARN), f"Case 08 FAILED: {r.errors}"

def test_case_09_deduplication():
    r = case_09_deduplication(); _print_case(r)
    assert r.status in (PASS, WARN), f"Case 09 FAILED: {r.errors}"

def test_case_10_provider_failure():
    r = case_10_provider_failure_graceful(); _print_case(r)
    assert r.status in (PASS, WARN), f"Case 10 FAILED: {r.errors}"


if __name__ == "__main__":
    run_all()
