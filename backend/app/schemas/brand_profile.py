from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ProductOneLiner(BaseModel):
    name: str
    one_liner: str


class ProjectOneLiner(BaseModel):
    name: str
    one_liner: str


class HardConstraints(BaseModel):
    never_invent: List[str] = Field(
        default_factory=lambda: [
            "Projects", "Clients", "Product specifications", "Product prices",
            "Performance claims", "Cost savings", "Time savings", "Material savings",
            "Founder experiences", "Founder opinions", "Awards", "Certifications",
            "Partnerships", "Project dates", "Project locations", "Machine capabilities"
        ]
    )
    product_naming: List[str] = Field(
        default_factory=lambda: [
            "Preserve ATON and ATOM as separate names.",
            "Do not silently merge product specifications.",
            "Use the exact name associated with the source/reference being used."
        ]
    )
    unknown_handling: str = "If the source does not establish a fact, mark it as unknown and do not guess."


class BrandProfileData(BaseModel):
    id: str = "default"
    company_name: str = "Kelvin6k"
    website: Optional[str] = "https://www.kelvin6k.com/"
    industry: str = "Construction 3D Printing / 3D Concrete Printing / Robotic Construction"
    brand_voice: str = "Technical, engineering-focused, innovative, confident, practical, and future-oriented"
    target_audience: str = "Construction 3D-printing companies, large-scale 3D concrete printing manufacturers, construction 3D-printing engineers, robotics engineers developing 3D-printing systems, concrete and printable-material researchers, structural engineers working on 3D-printed structures, researchers developing 3D-printing techniques, and companies developing 3D-printing hardware, software, materials, and robotic systems for construction."
    brand_principle: str = "Real construction robotics deployed in real environments."
    post_length: str = "medium"
    image_primary_provider: str = "openai"
    image_openai_model: str = "gpt-image-1-mini"
    image_openai_quality: str = "medium"
    competitors: List[str] = Field(
        default_factory=lambda: [
            "ICON", "COBOD", "PERI 3D Construction Printing", "Apis Cor",
            "SQ4D", "CyBe Construction", "WASP", "Contour Crafting"
        ]
    )
    products: List[ProductOneLiner] = Field(
        default_factory=lambda: [
            ProductOneLiner(name="ATOM", one_liner="Compact polar-based construction 3D-printing robot."),
            ProductOneLiner(name="ATON", one_liner="Large-format construction 3D-printing robot."),
            ProductOneLiner(name="G.MINI", one_liner="Compact laboratory/research 3D concrete printer.")
        ]
    )
    projects: List[ProjectOneLiner] = Field(
        default_factory=lambda: [
            ProjectOneLiner(name="MES Projects", one_liner="Defense/security infrastructure — Guard Rooms, Sentry Posts, Runway infrastructure."),
            ProjectOneLiner(name="GCC Bus-Stop Project", one_liner="3D-printed urban public transport bus shelter for municipal infrastructure."),
            ProjectOneLiner(name="ZOHO Project", one_liner="Off-site and on-site sustainable 3D-printed architectural elements for corporate campus."),
            ProjectOneLiner(name="THE ARC", one_liner="Large-span curved architectural showcase built with robotic precision printing.")
        ]
    )
    hard_constraints: HardConstraints = Field(default_factory=HardConstraints)
    reference_images: List[str] = Field(default_factory=list)

    # Optional social / approval fields
    instagram_handle: Optional[str] = None
    linkedin_handle: Optional[str] = None
    approval_channel: Optional[str] = "none"
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_webhook_secret: Optional[str] = None
    updated_at: Optional[str] = None


class BrandProfileRequest(BaseModel):
    company_name: str
    website: Optional[str] = None
    industry: str
    brand_voice: Optional[str] = None
    target_audience: str
    brand_principle: Optional[str] = None
    post_length: Optional[str] = "medium"
    image_primary_provider: Optional[str] = "openai"
    image_openai_model: Optional[str] = "gpt-image-1-mini"
    image_openai_quality: Optional[str] = "medium"
    competitors: List[str] = Field(default_factory=list)
    products: List[ProductOneLiner] = Field(default_factory=list)
    projects: List[ProjectOneLiner] = Field(default_factory=list)
    hard_constraints: Optional[HardConstraints] = Field(default_factory=HardConstraints)
    reference_images: List[str] = Field(default_factory=list)
    instagram_handle: Optional[str] = None
    linkedin_handle: Optional[str] = None
    approval_channel: Optional[str] = "none"
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_webhook_secret: Optional[str] = None
