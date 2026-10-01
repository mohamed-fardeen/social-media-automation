import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Supabase Settings
    SUPABASE_URL: str = "https://kdnbwgeofduhkmvbyuul.supabase.co"
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_ANON_KEY: str = "sb_publishable_iiId9oyHCGlvQ-Xg7oPiUA_EXuhRpuM"

    # Groq API Settings (Primary LLM Engine)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

    # Gemini Settings (Embeddings + Primary Image Generation)
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_IMAGE_API_KEY: Optional[str] = None   # Dedicated key for Imagen 3; falls back to GEMINI_API_KEY
    GEMINI_VISUAL_API_KEY: Optional[str] = None  # Dedicated visual/image generation key
    GEMINI_TEXT_API_KEY: Optional[str] = None    # Dedicated text reasoning key
    GEMINI_IMAGE_MODEL: str = "gemini-3.1-flash-image"
    GEMINI_TEXT_MODEL: str = "gemini-3.6-flash"
    # Optional local service that owns an authenticated Gemini Web browser session.
    # It receives a prompt and returns JSON containing image_base64.
    GEMINI_WEB_BRIDGE_URL: Optional[str] = None
    GEMINI_WEB_BRIDGE_TOKEN: Optional[str] = None

    # Cloudflare Workers AI (Image Generation Fallback)
    CF_ACCOUNT_ID: str = ""
    CF_API_TOKEN: str = ""
    CF_IMAGE_MODEL: str = "@cf/black-forest-labs/flux-1-schnell"

    # xAI Grok Settings (Fallback)
    XAI_API_KEY: str = ""
    XAI_MODEL: str = "grok-beta"
    XAI_BASE_URL: str = "https://api.x.ai/v1"

    # Embeddings (Google Gemini Embeddings)
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    EMBEDDING_DIMENSION: int = 384

    # OCR Settings
    OCR_PROVIDER: str = "tesseract"

    # External Research APIs
    TAVILY_API_KEY: Optional[str] = None
    APIFY_API_TOKEN: Optional[str] = None
    FIRECRAWL_API_KEY: Optional[str] = None
    LINKEDIN_API_KEY: Optional[str] = None
    IMAGE_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

    # Apify Actor Configurations
    APIFY_INSTAGRAM_ACTOR: str = "apify/instagram-hashtag-scraper"
    APIFY_REDDIT_ACTOR: str = ""
    APIFY_TWITTER_ACTOR: str = ""

    # Social Media Publishing
    INSTAGRAM_ACCESS_TOKEN: Optional[str] = None
    INSTAGRAM_BUSINESS_ACCOUNT_ID: Optional[str] = None
    LINKEDIN_ACCESS_TOKEN: Optional[str] = None
    LINKEDIN_ORGANIZATION_ID: Optional[str] = None

    # Telegram approvals
    TELEGRAM_PUBLIC_WEBHOOK_BASE: Optional[str] = None
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = None

    # Application Configuration
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000", "*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

