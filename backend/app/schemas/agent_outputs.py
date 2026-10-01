from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.editorial import (
    EditorialBrief,
    ContentOpportunity,
    ContentMemoryItem,
    ContentPortfolioSummary,
    VisualSpecification,
    ContentQAResult,
    VisionQAResult,
    CombinedQAResult,
    ClaimEvidenceItem,
    SourceType,
    ProofLevel,
    VisualType,
    ClaimType,
)

class StrategyOutput(BaseModel):
    topic: str = Field(description="Selected core topic for the campaign")
    angle: str = Field(description="Unique narrative angle or perspective")
    content_objective: str = Field(description="Primary objective (brand awareness, authority, engagement)")
    target_audience: str = Field(description="Target audience demographic and interests")
    recommended_format: str = Field(description="Visual format (carousel, infographic, hero image)")

class CopywriterOutput(BaseModel):
    instagram_caption: str = Field(description="Engaging Instagram caption with hook, value, and CTA")
    instagram_hashtags: List[str] = Field(description="List of 5 to 15 relevant Instagram hashtags")
    linkedin_post: str = Field(description="Professional, well-structured LinkedIn post text")
    linkedin_hashtags: List[str] = Field(description="3 to 5 targeted LinkedIn hashtags")
    cta: str = Field(description="Call to action statement")
    reasoning: str = Field(description="Strategic explanation for the copywriting decisions")
    supported_claims: List[str] = Field(default_factory=list, description="Verified claims in the copy")
    unsupported_claims: List[str] = Field(default_factory=list, description="Unsupported claims identified or removed")

class VisualOutput(BaseModel):
    concept: str = Field(description="Core visual concept and composition description")
    image_prompt: str = Field(description="Detailed image generation prompt optimized for AI generator")
    style: str = Field(description="Artistic style (photorealistic, vector, minimal, glassmorphic)")
    visual_spec: Optional[VisualSpecification] = Field(default=None, description="Detailed visual blueprint")

class ResearchOutput(BaseModel):
    trends: List[str] = Field(default_factory=list)
    competitor_signals: List[str] = Field(default_factory=list)
    industry_topics: List[str] = Field(default_factory=list)
    summary: str = Field(description="Concise synthesis of research findings")

