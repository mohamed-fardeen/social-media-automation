from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field

from app.schemas.brand_profile import BrandProfileData

PlatformType = Literal["instagram", "linkedin"]
RunStatusType = Literal[
    "queued", "researching", "strategizing", "writing",
    "designing", "generating_image", "awaiting_approval",
    "publishing", "published", "rejected", "failed"
]
DraftStatusType = Literal["draft", "pending_approval", "approved", "rejected", "published"]
DocumentStatusType = Literal["uploading", "processing", "indexing", "indexed", "failed"]

class IngestRequest(BaseModel):
    source: str = Field(default="document")
    filename: Optional[str] = None
    storage_path: Optional[str] = None
    url: Optional[str] = None
    text: Optional[str] = None
    brand_id: Optional[str] = None

class RunCreateRequest(BaseModel):
    brand_id: Optional[str] = None
    platforms: Optional[List[PlatformType]] = Field(default=["instagram", "linkedin"])
    topic: Optional[str] = None
    notes: Optional[str] = None
    mode: Literal["full_pipeline", "draft_only"] = "full_pipeline"
    image_mode: Optional[Literal["text_only", "with_image", "mix"]] = "with_image"
    source_mode: Optional[Literal["research", "user_topic"]] = "research"
    user_topic: Optional[str] = None
    country_scope: Optional[Literal["global", "india"]] = "global"
    trigger: Optional[str] = "manual"

class ResearchRunRequest(BaseModel):
    topic: Optional[str] = Field(default=None, max_length=500)
    platforms: Optional[List[str]] = Field(default=None)
    country_scope: Literal["global", "india"] = "global"
    max_results: int = Field(default=10, ge=1, le=20)

class ApprovalActionRequest(BaseModel):
    draft_id: Optional[str] = None
    action: Literal["approve", "reject", "regenerate", "dismiss"]
    feedback: Optional[str] = None
    platform: Optional[PlatformType] = None
    decided_by: Optional[str] = "user"


class IdeaSelectionRequest(BaseModel):
    choice: str
    decided_by: Optional[str] = "telegram"


class ChatRunRequest(BaseModel):
    """Conversational entry-point request from the web modal."""
    brand_id: Optional[str] = None
    platforms: Optional[List[Literal["instagram", "linkedin"]]] = ["linkedin"]
    source: Literal["research", "user_topic"]
    user_topic: Optional[str] = None
    image_mode: Literal["text_only", "with_image", "mix"] = "with_image"
    country_scope: Optional[Literal["global", "india"]] = "global"
    mode: Literal["full_pipeline", "draft_only"] = "draft_only"
    trigger: Optional[str] = "web_modal"


class RegenerateFeedbackRequest(BaseModel):
    feedback: str = Field(min_length=1, max_length=2000)


class RagChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    document_id: Optional[str] = None
    match_count: int = Field(default=8, ge=1, le=20)

class BrandProfileRequest(BaseModel):
    company_name: str = Field(
        min_length=1,
        max_length=160
    )

    industry: str = Field(
        min_length=1,
        max_length=300
    )

    website: Optional[str] = Field(
        default=None,
        max_length=300
    )

    instagram_handle: Optional[str] = Field(
        default=None,
        max_length=120
    )

    linkedin_handle: Optional[str] = Field(
        default=None,
        max_length=180
    )

    approval_channel: Optional[str] = Field(
        default="none",
        max_length=32
    )

    telegram_bot_token: Optional[str] = Field(
        default=None,
        max_length=500
    )

    telegram_chat_id: Optional[str] = Field(
        default=None,
        max_length=200
    )

    telegram_webhook_secret: Optional[str] = Field(
        default=None,
        max_length=200
    )

    profile_data: BrandProfileData

class TelegramConnectRequest(BaseModel):
    telegram_bot_token: str = Field(min_length=1, max_length=500)
    telegram_chat_id: str = Field(min_length=1, max_length=200)
    telegram_webhook_secret: Optional[str] = Field(default=None, max_length=200)
    approval_channel: Optional[str] = Field(default="telegram", max_length=32)

class StandardResponse(BaseModel):
    ok: bool = True
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
