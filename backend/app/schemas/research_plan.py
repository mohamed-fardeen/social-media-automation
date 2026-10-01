"""
Pydantic Schemas for Research Planner, Normalized Evidence, and Provider Routing.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class SocialSearchTarget(BaseModel):
    platform: str = Field(description="Target platform: instagram, reddit, x, linkedin")
    query_or_handle: str = Field(description="Query string, hashtag, or target profile handle")
    target_type: str = Field(default="search", description="search, profile, or hashtag")


class ResearchPlan(BaseModel):
    summary_of_intent: str = Field(description="Brief explanation of research strategy and objectives")
    web_queries: List[str] = Field(default_factory=list, description="General web search queries for Tavily")
    target_urls: List[str] = Field(default_factory=list, description="Specific URLs requiring deep Markdown extraction via Firecrawl")
    social_targets: List[SocialSearchTarget] = Field(default_factory=list, description="Platform-specific social media targets for Apify / Official APIs")
    needs_deep_crawl: bool = Field(default=False, description="True if detailed site crawling is required")


class ResearchDocument(BaseModel):
    id: str = Field(description="Unique document or chunk ID")
    title: str = Field(default="", description="Article or post title")
    url: str = Field(description="Canonical source URL")
    content: str = Field(description="Cleaned text content or Markdown summary")
    provider: str = Field(description="Provider name: tavily, firecrawl, apify, linkedin_official, mock")
    platform: str = Field(default="web", description="Target platform: web, instagram, reddit, x, linkedin")
    scraped_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    score: float = Field(default=0.5, description="Relevance score (0.0 to 1.0)")
    engagement: Optional[Dict[str, Any]] = Field(default=None, description="Optional social metrics (likes, comments, shares)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional provenance or provider metadata")
