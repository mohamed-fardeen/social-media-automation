"""
FastAPI application entry point for Kelvin6k Social Engine V2 Backend.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config.settings import settings
from app.config.logging import logger
from app.api.v1 import router as v1_router
from app.api.webhooks import router as webhooks_router


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Kelvin6k Backend V2 starting up…")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Model: {settings.GROQ_MODEL} (Groq Cloud)")
    logger.info(f"Embedding: {settings.EMBEDDING_MODEL} (dim={getattr(settings, 'EMBEDDING_DIMENSION', 384)})")
    logger.info(f"OCR Provider: {settings.OCR_PROVIDER}")

    # 1. Database & Vector Search Verification
    from app.database.supabase_client import get_supabase_client
    supa = get_supabase_client()
    if supa:
        logger.info("Supabase connected ✓")
        try:
            from app.services.rag.embedder import EmbeddingProvider
            embedder = EmbeddingProvider()
            test_v = embedder.embed("health check")
            if test_v:
                rpc_test = supa.rpc("match_knowledge_chunks", {
                    "query_embedding": test_v,
                    "match_threshold": 0.1,
                    "match_count": 1
                }).execute()
                logger.info(f"Vector search verified ✓ (Dimension: {len(test_v)})")
        except Exception as v_err:
            logger.warning(f"[STARTUP WARNING] Vector similarity search check: {v_err}")
    else:
        logger.warning("Supabase not configured — running in local fallback mode.")

    # 2. Image Provider Health Check
    try:
        from app.services.image.generator import check_image_providers_health
        img_health = check_image_providers_health()
        logger.info(f"Image generation providers configured: {list(img_health.keys())}")
    except Exception as img_err:
        logger.warning(f"Image generation health check failed: {img_err}")

    # 3. Schedule Background Tasks
    try:
        from app.services.prune import run_pruning_job_async
        run_pruning_job_async()
        logger.info("Background DB pruning scheduled ✓")
    except Exception as e:
        logger.warning(f"Failed to schedule pruning job: {e}")
        logger.warning(f"[STARTUP WARNING] Image provider health check error: {img_err}")

    # 3. Telegram Polling
    if not settings.TELEGRAM_PUBLIC_WEBHOOK_BASE and supa:
        try:
            from app.services.brand_profile import get_brand_profile
            from app.services.telegram_bot import start_local_polling

            profile = get_brand_profile()
            bot_token = (profile or {}).get("telegram_bot_token")
            if bot_token:
                start_local_polling(bot_token)
        except Exception as e:
            logger.warning(f"Telegram local polling startup skipped: {e}")
    yield
    try:
        from app.services.telegram_bot import stop_local_polling

        stop_local_polling()
    except Exception:
        pass
    # Shutdown (nothing to clean up currently)
    logger.info("Kelvin6k Backend V2 shutting down.")


# ─── App Creation ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="Kelvin6k Social Engine V2",
    description="Production backend for Kelvin6k AI Social Media Engine. "
                "FastAPI + LangGraph + Supabase + Groq (Llama 3.3 70B Versatile).",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# ─── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ─── Routes ───────────────────────────────────────────────────────────────────

# Versioned REST API
app.include_router(v1_router, prefix="/api/v1")

# Legacy n8n webhook compatibility (frontend calls these URLs directly)
app.include_router(webhooks_router, prefix="/webhook")

# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    from app.database.supabase_client import get_supabase_client
    supa = get_supabase_client()
    return {
        "status": "ok",
        "version": "2.0.0",
        "supabase": "connected" if supa else "unavailable",
        "environment": settings.ENVIRONMENT
    }


@app.get("/")
async def root():
    return {
        "name": "Kelvin6k Social Engine V2",
        "docs": "/docs",
        "health": "/health"
    }
