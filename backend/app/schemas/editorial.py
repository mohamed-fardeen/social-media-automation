"""
Editorial and Content Intelligence Schemas for Kelvin6k Social Engine.
Defines typed models for Editorial Brief, Content Opportunities, Content Memory,
Claim Grounding, Visual Specifications, and Quality Assurance.
"""
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


SourceType = Literal[
    "COMPANY_TRUTH",
    "PROJECT_TRUTH",
    "INDUSTRY_RESEARCH",
    "COMPETITOR_INFORMATION"
]

ProofLevel = Literal[
    "verified_project",
    "lab_proven",
    "industry_benchmark",
    "strategic_perspective"
]

VisualType = Literal[
    "real_project_photography",
    "machine_photography",
    "printing_process",
    "engineering_cutaway",
    "technical_diagram",
    "before_after",
    "comparison",
    "product_visualization",
    "conceptual_visualization",
    "architectural_photography",
    "text_only"
]

ClaimType = Literal[
    "SUPPORTED_CLAIM",
    "UNSUPPORTED_CLAIM",
    "INFERENCE",
    "OPINION"
]

DecisionType = Literal["PASS", "REVISE", "REJECT"]


class ClaimEvidenceItem(BaseModel):
    statement: str = Field(description="The factual claim or assertion made in the post")
    claim_type: ClaimType = Field(default="SUPPORTED_CLAIM", description="Claim classification")
    source_type: Optional[SourceType] = Field(default=None, description="Truth category of the evidence")
    source_citation: Optional[str] = Field(default=None, description="Citation / document source reference")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Verification confidence score")
    supported: bool = Field(default=True, description="Whether the claim is grounded in verified evidence")


class EditorialBrief(BaseModel):
    """
    The central, authoritative single source of truth produced after idea selection.
    Guides both Copywriting and Visual Direction agents.
    """
    topic: str = Field(description="Core technical or industry topic")
    core_message: str = Field(description="The single fundamental insight or argument")
    why_it_matters: str = Field(description="Why this matters to structural engineers, builders, and roboticists")
    target_audience: str = Field(description="Target audience segment and context")
    evidence: List[Dict[str, Any]] = Field(default_factory=list, description="Verified supporting data points with source provenance")
    kelvin6k_connection: str = Field(description="Direct, verified connection to Kelvin6k products (ATON/ATOM/G.MINI) or projects (MES/ZOHO/GCC/ARC)")
    proof_level: ProofLevel = Field(default="industry_benchmark", description="Level of empirical proof backing the core message")
    supported_claims: List[str] = Field(default_factory=list, description="Verified claims that can be safely asserted")
    unsupported_claims: List[str] = Field(default_factory=list, description="Unsubstantiated claims that MUST be avoided or framed as opinion")
    tone: str = Field(default="Authoritative, concise, engineering-focused B2B", description="Tone and register of the post")
    content_type: str = Field(default="technical_insight", description="Nature of content: technical_insight, project_story, comparison, educational")
    format: str = Field(default="insight", description="Format identifier (e.g. data_snack, comparison, case_study, carousel, founder_pov)")
    cta: str = Field(default="", description="Relevant discussion hook or call to action")
    visual_story: str = Field(description="What physical mechanism or result must the visual communicate to the viewer")
    visual_type: VisualType = Field(default="architectural_photography", description="Selected category of visual")
    visual_requirements: List[str] = Field(default_factory=list, description="Must-include visual elements (e.g. layer striations, nozzle, site context)")
    visual_negatives: List[str] = Field(default_factory=list, description="Explicit exclusions (e.g. smooth drywall, neon lights, CGI gloss, unrelated machines)")


class ContentOpportunity(BaseModel):
    """
    Structured evaluation of a candidate post topic/angle produced by Content Intelligence.
    """
    topic: str = Field(description="Topic or development under evaluation")
    relevance: float = Field(ge=1.0, le=10.0, description="Relevance to 3D concrete printing & construction robotics")
    novelty: float = Field(ge=1.0, le=10.0, description="Novelty compared to recent industry discourse and previous posts")
    evidence_strength: float = Field(ge=1.0, le=10.0, description="Empirical strength and verifiability of research evidence")
    audience_value: float = Field(ge=1.0, le=10.0, description="Practical value to engineers, architects, and contractors")
    specificity: float = Field(ge=1.0, le=10.0, description="Depth of technical specificity vs generic platitudes")
    brand_fit: float = Field(ge=1.0, le=10.0, description="Alignment with Kelvin6k positioning and capabilities")
    visual_potential: float = Field(ge=1.0, le=10.0, description="Feasibility of creating clear visual proof")
    credibility_risk: float = Field(ge=1.0, le=10.0, description="Risk of overpromising or making unsupported technical claims (1=low risk, 10=high risk)")
    overall_score: float = Field(ge=0.0, le=10.0, description="Weighted composite score")
    reasoning: str = Field(description="Detailed evaluation rationale")
    decision: Literal["ACCEPT", "REJECT", "NARROW"] = Field(description="Whether to proceed with this opportunity")


class ContentMemoryItem(BaseModel):
    """
    Historical post memory item used for semantic repetition and portfolio tracking.
    """
    id: Optional[str] = None
    topic: str
    core_message: Optional[str] = None
    angle: Optional[str] = None
    content_type: Optional[str] = None
    format: Optional[str] = None
    product: Optional[str] = None
    project: Optional[str] = None
    audience: Optional[str] = None
    major_claims: List[str] = Field(default_factory=list)
    visual_concept: Optional[str] = None
    published_at: Optional[str] = None
    similarity_score: Optional[float] = None


class ContentPortfolioSummary(BaseModel):
    """
    Overview of recent content coverage across key categories to prevent topic fatigue.
    """
    products_distribution: Dict[str, int] = Field(default_factory=dict)
    projects_distribution: Dict[str, int] = Field(default_factory=dict)
    tech_distribution: Dict[str, int] = Field(default_factory=dict)
    industry_distribution: Dict[str, int] = Field(default_factory=dict)
    proof_distribution: Dict[str, int] = Field(default_factory=dict)
    recent_topics: List[str] = Field(default_factory=list)


class VisualSpecification(BaseModel):
    """
    Detailed technical visual blueprint generated by the Visual Director.
    """
    subject: str = Field(description="Main subject of the image")
    visual_type: VisualType = Field(default="architectural_photography", description="Type of visual")
    core_understanding: str = Field(description="What must the viewer understand in the first 2 seconds")
    physical_demonstration: str = Field(description="What physical object, toolpath, machine, or structure demonstrates the insight")
    key_elements_visible: List[str] = Field(default_factory=list, description="Elements that must be explicitly visible")
    elements_not_visible: List[str] = Field(default_factory=list, description="Elements that must NOT be visible")
    is_3dcp_relevant: bool = Field(default=True, description="Whether 3D concrete printing authenticity rules apply")
    authenticity_details: List[str] = Field(default_factory=list, description="Specific 3DCP authenticity cues (layer beads, mortar texture, nozzle, etc.)")
    machine_reference: Optional[str] = Field(default=None, description="Referenced machine ('aton', 'atom', 'gmini', or None)")
    image_prompt: str = Field(description="Exact prompt to pass to the image generation provider")
    aspect_ratio: str = Field(default="1:1", description="Target aspect ratio")
    is_text_only: bool = Field(default=False, description="True if no image should be rendered")
    requires_post_label_overlay: bool = Field(default=False, description="True if text labels should be overlaid post-generation rather than rendered by image model")
    label_overlay_spec: Optional[List[Dict[str, str]]] = Field(default=None, description="List of label overlays: [{'text': '...', 'position': 'top-left|top-right|bottom-left|bottom-right'}]")
    slide_specifications: Optional[List[Dict[str, Any]]] = Field(default=None, description="Multi-slide specifications if format is carousel")


class ContentQAResult(BaseModel):
    """
    Quality control evaluation of written copy.
    """
    accuracy_score: float = Field(ge=1.0, le=10.0, description="Adherence to verified claims without hallucination")
    clarity_score: float = Field(ge=1.0, le=10.0, description="Readability and logical structure")
    professionalism_score: float = Field(ge=1.0, le=10.0, description="B2B engineering voice (sounds like COBOD/PERI/Tvasta)")
    conciseness_score: float = Field(ge=1.0, le=10.0, description="Density of insight without filler or fluff")
    novelty_score: float = Field(ge=1.0, le=10.0, description="Freshness compared to past Kelvin6k posts")
    brand_fit_score: float = Field(ge=1.0, le=10.0, description="Reinforces Kelvin6k positioning without forced promo")
    evidence_score: float = Field(ge=1.0, le=10.0, description="Adequacy of concrete evidence backing arguments")
    hook_score: float = Field(ge=1.0, le=10.0, description="Effectiveness of opening line for stopping the scroll")
    naturalness_score: float = Field(ge=1.0, le=10.0, description="Sounds human and authentic rather than generic AI")
    self_promotion_score: float = Field(ge=1.0, le=10.0, description="Appropriate moderation of brand mentions (10=tasteful, 1=overly salesy)")
    overall_score: float = Field(ge=0.0, le=10.0, description="Weighted composite score")
    decision: DecisionType = Field(description="PASS, REVISE, or REJECT")
    issues: List[str] = Field(default_factory=list, description="Specific identified issues")
    required_changes: List[str] = Field(default_factory=list, description="Targeted instructions for revision")


class VisionQAResult(BaseModel):
    """
    Vision-based quality control evaluation of the generated image.
    """
    technical_accuracy: float = Field(ge=1.0, le=10.0, description="Physics, structural, and mechanical believability")
    authenticity_3dcp: float = Field(ge=1.0, le=10.0, description="Layer bead striations, mortar texture, formwork-free geometry")
    concept_alignment: float = Field(ge=1.0, le=10.0, description="Matches the core message in the Editorial Brief")
    caption_alignment: float = Field(ge=1.0, le=10.0, description="Directly illustrates or proves what the caption discusses")
    machine_accuracy: float = Field(ge=1.0, le=10.0, description="Accurate representation of referenced machines if present")
    composition: float = Field(ge=1.0, le=10.0, description="Lighting, focal point, visual hierarchy")
    visual_clarity: float = Field(ge=1.0, le=10.0, description="Legibility of physical features without muddiness")
    text_rendering_check: float = Field(default=10.0, ge=1.0, le=10.0, description="Absence of garbled or nonsensical pseudo-text artifacts (10=clean/no text artifacts, 1=severe garbled text)")
    no_humans_check: float = Field(default=10.0, ge=1.0, le=10.0, description="Absence of human figures/faces/workers (10=pure architectural/machine scene with zero humans, 1=prominent humans)")
    brand_fit: float = Field(ge=1.0, le=10.0, description="Fits Kelvin6k aesthetic (real engineering, not sci-fi/CGI)")
    realism: float = Field(ge=1.0, le=10.0, description="Photographic or technical plausibility")
    overall_score: float = Field(ge=0.0, le=10.0, description="Weighted composite score")
    decision: DecisionType = Field(description="PASS, REVISE, or REJECT")
    issues: List[str] = Field(default_factory=list, description="Identified visual defects or misalignments")
    retry_prompt_adjustments: Optional[str] = Field(default=None, description="Adjustments for image regeneration if needed")


class CombinedQAResult(BaseModel):
    """
    Final multi-gate QA outcome gating publication or human approval.
    """
    passed: bool = Field(description="True if content QA, vision QA (if applicable), and claim grounding all pass")
    content_qa: ContentQAResult
    vision_qa: Optional[VisionQAResult] = None
    claim_grounding_passed: bool = True
    summary: str = Field(description="Summary of QA review")
