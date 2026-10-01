from typing import Optional, List, Dict, Any
from typing_extensions import TypedDict


class RunState(TypedDict):
    # Run identity
    run_id: str
    brand_id: Optional[str]
    platforms: List[str]
    mode: Optional[str]

    # Topic pipeline
    topic_hint: Optional[str]
    topic: Optional[str]
    angle: Optional[str]

    # Agent contexts
    research_context: Optional[str]       # Synthesized research summary
    research_evidence: Optional[List[Dict[str, Any]]] # Transient per-run research documents with provenance
    knowledge_context: Optional[str]      # Retrieved RAG chunks summary
    knowledge_citations: List[str]        # Source labels from knowledge store

    # Content Intelligence & Memory Layer
    content_opportunities: Optional[List[Dict[str, Any]]] # Evaluated candidate opportunities with scores
    content_memory: Optional[List[Dict[str, Any]]]        # Retrieved semantically similar previous posts
    content_portfolio: Optional[Dict[str, Any]]           # Recent category distribution (products/projects/tech/industry)
    repetition_warning: Optional[str]                     # Flag if high similarity with recent posts

    # Strategy
    strategy: Optional[str]
    content_objective: Optional[str]
    target_audience: Optional[str]
    prefetched_ideas: Optional[List[Dict[str, Any]]]

    # Editorial Brief (Single Source of Truth after idea selection)
    editorial_brief: Optional[Dict[str, Any]] # Structured EditorialBrief dict
    claim_evidence: Optional[List[Dict[str, Any]]] # Traceable claims and grounding

    # Generated content
    instagram_draft: Optional[str]
    instagram_hashtags: List[str]
    linkedin_draft: Optional[str]
    linkedin_hashtags: List[str]
    cta: Optional[str]

    # Visual / image
    visual_spec: Optional[Dict[str, Any]]     # Structured VisualSpecification
    visual_prompt: Optional[str]
    image_url: Optional[str]
    image_provider_used: Optional[str]        # Provider that generated the image (e.g. "GeminiImageProvider", "CloudflareImageProvider")
    referenced_product: Optional[str]

    # Quality Assurance (Content QA + Vision QA)
    content_qa: Optional[Dict[str, Any]]      # ContentQAResult dict
    visual_qa: Optional[Dict[str, Any]]       # VisionQAResult dict
    qa_passed: Optional[bool]                 # True if all QA checks pass
    qa_status: Optional[str]                  # "verified_pass" | "fallback_pass_unverified" | "revise" | "reject"
    qa_issues: List[str]                      # Aggregated issues if any
    degraded_steps: List[str]                 # Steps that used fallback heuristic or repair

    # Approval / versioning
    status: str                           # mirrors RunStatus
    feedback: Optional[str]              # User feedback for regeneration
    version: int

    # Idea selection (Telegram-driven)
    ideas: Optional[List[Dict[str, Any]]]   # 3 candidate ideas (set by ideation_node)
    selected_idea_indices: List[int]        # user-picked indices for this run
    current_idea_index: Optional[int]       # which idea the current copy→save pass is producing for

    # Per-idea format (set when the user picks an idea; threaded into copywriter + visual)
    format: Optional[str]                   # e.g. "case_study", "carousel", "founder_pov"
    format_label: Optional[str]             # human-readable label, e.g. "5-slide carousel"
    image_hint: Optional[str]               # visual direction for the image generation agent

    # Conversational entry-point state (set at /draft / run-now)
    image_mode: Optional[str]               # "text_only" | "with_image" | "mix"
    source_mode: Optional[str]              # "research" | "user_topic"
    user_topic: Optional[str]               # topic typed by the user when source_mode == "user_topic"
    country_scope: Optional[str]            # "global" | "india"

    # Draft IDs (after Save Draft node)
    draft_ids: List[str]

    # Error tracking
    errors: List[str]

    # Internal notes/reasoning summaries for observability
    notes: Optional[str]

    # Run trigger: "telegram" | "web_modal" | "manual" — controls which output
    # channels receive notifications. MUST be declared here so LangGraph carries
    # it through all nodes (keys not in the TypedDict are silently dropped).
    trigger: Optional[str]

