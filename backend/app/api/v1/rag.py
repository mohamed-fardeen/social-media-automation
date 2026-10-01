from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from app.schemas.api import RagChatRequest, StandardResponse
from app.database.supabase_client import get_supabase_client
from app.services.llm.groq import GroqLLM
from app.services.rag.store import KnowledgeStore
from app.services.rag.health import validate_rag_health
from app.services.brand_profile import format_brand_context, get_brand_profile
from app.services.entity_suggestions import list_pending_suggestions, approve_suggestion, ignore_suggestion
from app.services.brand_reference_images import list_all_reference_images, add_reference_image

router = APIRouter()


class ReferenceImageCreateRequest(BaseModel):
    image_url: str
    linked_to_type: str  # 'product' | 'project'
    linked_to_name: str


@router.get("/health", response_model=StandardResponse)
async def rag_health():
    """Diagnostic check for RAG embeddings and database vector configuration."""
    health_data = validate_rag_health()
    return StandardResponse(ok=health_data.get("status") == "healthy", data=health_data)


# ── Entity Suggestions Endpoints ─────────────────────────────────────────────

@router.get("/suggestions", response_model=StandardResponse)
async def get_suggestions(status: Optional[str] = "pending"):
    """List entity suggestions extracted from uploaded documents."""
    suggestions = list_pending_suggestions(status=status)
    return StandardResponse(ok=True, data={"suggestions": suggestions})


@router.post("/suggestions/{suggestion_id}/approve", response_model=StandardResponse)
async def approve_entity_suggestion(suggestion_id: str):
    """Approve an entity suggestion and append it to the Brand Profile (products/projects)."""
    updated = approve_suggestion(suggestion_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Suggestion not found.")
    return StandardResponse(ok=True, data={"suggestion": updated, "profile": get_brand_profile()})


@router.post("/suggestions/{suggestion_id}/ignore", response_model=StandardResponse)
async def ignore_entity_suggestion(suggestion_id: str):
    """Dismiss/ignore an entity suggestion."""
    updated = ignore_suggestion(suggestion_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Suggestion not found.")
    return StandardResponse(ok=True, data={"suggestion": updated})


# ── Reference Images Endpoints ───────────────────────────────────────────────

@router.get("/reference-images", response_model=StandardResponse)
async def get_reference_images():
    """List all stored brand reference images with their linked product/project."""
    images = list_all_reference_images()
    return StandardResponse(ok=True, data={"reference_images": images})


@router.post("/reference-images", response_model=StandardResponse)
async def create_reference_image(payload: ReferenceImageCreateRequest):
    """Create / link a reference image to a product or project."""
    record = add_reference_image(
        image_url=payload.image_url,
        linked_to_type=payload.linked_to_type,
        linked_to_name=payload.linked_to_name
    )
    return StandardResponse(ok=True, data={"reference_image": record})


@router.post("/reference-images/upload", response_model=StandardResponse)
async def upload_reference_image_file(
    file: UploadFile = File(...),
    linked_to_type: str = Form(...),
    linked_to_name: str = Form(...)
):
    """Directly upload a reference image to storage and link it."""
    import uuid
    import mimetypes
    from app.database.supabase_client import get_supabase_client

    filename = file.filename or "reference.jpg"
    file_bytes = await file.read()
    mime = file.content_type or mimetypes.guess_type(filename)[0] or "image/jpeg"
    file_id = str(uuid.uuid4())[:8]
    storage_path = f"brand-assets/references/{file_id}_{filename}"

    supa = get_supabase_client()
    public_url = None
    if supa:
        try:
            supa.storage.from_("brand-assets").upload(
                storage_path, file_bytes, {"content-type": mime}
            )
            public_url = supa.storage.from_("brand-assets").get_public_url(storage_path)
        except Exception:
            # Fallback upload to post-media
            try:
                supa.storage.from_("post-media").upload(
                    storage_path, file_bytes, {"content-type": mime}
                )
                public_url = supa.storage.from_("post-media").get_public_url(storage_path)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Image upload failed: {e}")

    if not public_url:
        public_url = f"/uploads/{filename}"

    record = add_reference_image(
        image_url=public_url,
        linked_to_type=linked_to_type,
        linked_to_name=linked_to_name
    )
    return StandardResponse(ok=True, data={"reference_image": record})


def _is_inventory_question(question: str) -> bool:
    q = question.lower()
    return any(phrase in q for phrase in [
        "what documents",
        "which documents",
        "document knowledge",
        "knowledge do you have",
        "what do you know",
        "indexed documents",
        "how many pages",
        "how many chunks",
    ])


def _document_inventory():
    supa = get_supabase_client()
    if not supa:
        return []

    docs_res = supa.table("documents").select("*").order("created_at", desc=True).execute()
    docs = docs_res.data or []
    inventory = []
    for doc in docs:
        chunks_res = supa.table("knowledge_chunks").select("metadata").eq("document_id", doc["id"]).execute()
        chunks = chunks_res.data or []
        pages = sorted({
            (chunk.get("metadata") or {}).get("page_number")
            for chunk in chunks
            if (chunk.get("metadata") or {}).get("page_number") is not None
        })
        inventory.append({
            "document_id": doc["id"],
            "file_name": doc.get("file_name"),
            "status": doc.get("status"),
            "chunks": len(chunks),
            "pages": pages,
            "page_count": len(pages),
        })
    return inventory


@router.post("/chat", response_model=StandardResponse)
async def rag_chat(payload: RagChatRequest):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")

    if _is_inventory_question(question):
        inventory = _document_inventory()
        indexed = [doc for doc in inventory if doc["chunks"] > 0]
        if not indexed:
            answer = "I do not have any indexed document chunks yet."
        else:
            lines = ["I currently have indexed knowledge from:"]
            for doc in indexed:
                pages = ", ".join(str(page) for page in doc["pages"]) or "no page metadata"
                lines.append(
                    f"- {doc['file_name']}: {doc['chunks']} chunks across {doc['page_count']} pages ({pages})."
                )
            answer = "\n".join(lines)
        return StandardResponse(ok=True, data={"answer": answer, "citations": [], "documents": inventory})

    store = KnowledgeStore()
    chunks = store.similarity_search(
        query=question,
        match_count=max(payload.match_count, 12),
        match_threshold=0.55,
        document_id_filter=payload.document_id
    )

    if not chunks:
        return StandardResponse(
            ok=True,
            data={
                "answer": "I could not find relevant indexed document context for that question yet.",
                "citations": [],
                "chunks": []
            }
        )

    context_blocks = []
    citations = []
    seen = set()
    for idx, chunk in enumerate(chunks, start=1):
        metadata = chunk.get("metadata") or {}
        source = metadata.get("source_label") or metadata.get("source_filename") or chunk.get("source_label") or "Indexed document"
        page = metadata.get("page_number")
        citation = {
            "index": idx,
            "source": source,
            "page": page,
            "similarity": chunk.get("similarity")
        }
        key = (source, page)
        if key not in seen:
            citations.append(citation)
            seen.add(key)

        page_label = f", page {page}" if page else ""
        context_blocks.append(
            f"[{idx}] Source: {source}{page_label}\n{chunk.get('content', '')[:1800]}"
        )

    system_prompt = (
        "You are a document RAG assistant. Answer only from the provided document context. "
        "Also use the company profile as standing background context when it helps interpret the documents. "
        "If the context is insufficient, say what is missing. Be concise and include bracketed "
        "citations like [1] or [2] for claims grounded in the context."
    )
    brand_context = format_brand_context(get_brand_profile())
    user_prompt = (
        "Company profile:\n"
        + brand_context
        + "\n\nDocument context:\n\n"
        + "\n\n".join(context_blocks)
        + f"\n\nQuestion: {question}"
    )

    llm = GroqLLM()
    answer = llm.chat(system_prompt, user_prompt, temperature=0.2, max_tokens=900)

    return StandardResponse(
        ok=True,
        data={
            "answer": answer,
            "citations": citations[:8],
            "chunks": chunks[:payload.match_count]
        }
    )
