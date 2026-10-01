from fastapi import APIRouter
from app.api.v1 import ingest, runs, documents, research, analytics, rag, brand

router = APIRouter()

router.include_router(ingest.router,    prefix="/ingest",    tags=["Ingest"])
router.include_router(runs.router,      prefix="/runs",      tags=["Runs"])
router.include_router(documents.router, prefix="/documents", tags=["Documents"])
router.include_router(research.router,  prefix="/research",  tags=["Research"])
router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
router.include_router(rag.router,       prefix="/rag",       tags=["RAG"])
router.include_router(brand.router,     prefix="/brand",     tags=["Brand"])
