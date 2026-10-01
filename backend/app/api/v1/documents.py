from fastapi import APIRouter, HTTPException
from app.schemas.api import StandardResponse
from app.database.supabase_client import get_supabase_client

router = APIRouter()


def _enrich_documents(supa, documents):
    enriched = []
    for doc in documents:
        chunks = []
        try:
            chunk_res = supa.table("knowledge_chunks") \
                .select("metadata") \
                .eq("document_id", doc["id"]) \
                .execute()
            chunks = chunk_res.data or []
        except Exception:
            chunks = []

        pages = {
            (chunk.get("metadata") or {}).get("page_number")
            for chunk in chunks
            if (chunk.get("metadata") or {}).get("page_number") is not None
        }

        enriched.append({
            **doc,
            "chunks": len(chunks),
            "pages": len(pages),
        })
    return enriched


@router.get("", response_model=StandardResponse)
async def list_documents():
    supa = get_supabase_client()
    if not supa:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        res = supa.table("documents") \
            .select("*") \
            .order("created_at", desc=True) \
            .execute()
        return StandardResponse(ok=True, data={"documents": _enrich_documents(supa, res.data or [])})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}", response_model=StandardResponse)
async def get_document(document_id: str):
    supa = get_supabase_client()
    if not supa:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        res = supa.table("documents").select("*").eq("id", document_id).single().execute()
        docs = _enrich_documents(supa, [res.data]) if res.data else []
        if not docs:
            raise HTTPException(status_code=404, detail="Document not found")
        return StandardResponse(ok=True, data={"document": docs[0]})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{document_id}", response_model=StandardResponse)
async def delete_document(document_id: str):
    supa = get_supabase_client()
    if not supa:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        doc_res = supa.table("documents").select("*").eq("id", document_id).single().execute()
        document = doc_res.data
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        supa.table("knowledge_chunks").delete().eq("document_id", document_id).execute()
        supa.table("documents").delete().eq("id", document_id).execute()

        storage_path = document.get("storage_path")
        if storage_path:
            try:
                supa.storage.from_("knowledge-uploads").remove([storage_path])
            except Exception:
                pass

        return StandardResponse(ok=True, data={"document_id": document_id})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
