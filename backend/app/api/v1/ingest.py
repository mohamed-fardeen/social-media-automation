"""
POST /api/v1/ingest — trigger document ingestion pipeline (OCR + chunk + embed).
"""
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from typing import Optional
from app.schemas.api import IngestRequest, StandardResponse
from app.database.supabase_client import get_supabase_client
from app.config.logging import logger

router = APIRouter()


async def _run_ingest_pipeline(document_id: str, storage_path: str, filename: str,
                               file_bytes: Optional[bytes] = None):
    """Background task: OCR → chunk → embed → store."""
    from datetime import datetime, timezone
    import mimetypes

    supa = get_supabase_client()
    now = datetime.now(timezone.utc).isoformat()

    def update_doc(patch: dict):
        if supa:
            try:
                supa.table("documents").update(patch).eq("id", document_id).execute()
            except Exception as e:
                logger.error(f"DB update failed for doc {document_id}: {e}")

    try:
        update_doc({"status": "processing"})

        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        pages = []

        # Download from Supabase storage if bytes not provided
        if not file_bytes and supa:
            logger.info(f"[ingest] {document_id}: downloading from storage path '{storage_path}'")
            try:
                res = supa.storage.from_("knowledge-uploads").download(storage_path)
                file_bytes = res
                logger.info(f"[ingest] {document_id}: downloaded {len(file_bytes)} bytes from Supabase storage")
            except Exception as dl_err:
                logger.error(f"[ingest] {document_id}: storage download failed: {dl_err}")

        if not file_bytes:
            raise ValueError("No file bytes available for processing.")

        logger.info(f"[ingest] {document_id}: processing '{filename}' ({len(file_bytes)} bytes, mime={mime})")

        # ── OCR-First Pipeline ───────────────────────────────────────────────
        if "pdf" in mime:
            logger.info(f"[ingest] {document_id}: using PDFProcessor")
            from app.services.pdf.pdf_processor import PDFProcessor
            processor = PDFProcessor()
            pages = processor.process_pdf(file_bytes, filename)
            logger.info(f"[ingest] {document_id}: PDF extracted {len(pages)} page(s)")
        elif mime.startswith("image/"):
            logger.info(f"[ingest] {document_id}: using OCR for image")
            from app.services.ocr.paddle_ocr import PaddleOCRProvider
            ocr = PaddleOCRProvider()
            results = ocr.extract_text_from_image(file_bytes, filename)
            pages = [{"page_number": r.page_number, "content": r.text,
                      "method": "ocr", "confidence": r.confidence, "filename": filename}
                     for r in results]
            logger.info(f"[ingest] {document_id}: image OCR yielded {len(pages)} result(s)")
        elif "word" in mime or "docx" in mime:
            logger.info(f"[ingest] {document_id}: using python-docx")
            try:
                import docx
                from io import BytesIO
                doc_obj = docx.Document(BytesIO(file_bytes))
                text = "\n".join([p.text for p in doc_obj.paragraphs if p.text.strip()])
                pages = [{"page_number": 1, "content": text,
                          "method": "native", "confidence": 1.0, "filename": filename}]
                logger.info(f"[ingest] {document_id}: docx extracted {len(text)} chars")
            except Exception as docx_err:
                logger.error(f"[ingest] {document_id}: docx extraction failed: {docx_err}")
                pages = []
        else:
            # Plain text / markdown / CSV
            logger.info(f"[ingest] {document_id}: treating as plain text")
            try:
                text = file_bytes.decode("utf-8", errors="replace")
                pages = [{"page_number": 1, "content": text,
                          "method": "native", "confidence": 1.0, "filename": filename}]
                logger.info(f"[ingest] {document_id}: plain text extracted {len(text)} chars")
            except Exception as txt_err:
                logger.error(f"[ingest] {document_id}: text decode failed: {txt_err}")
                pages = []

        if not pages:
            raise ValueError("No content could be extracted from the document.")

        non_empty = [p for p in pages if p.get("content", "").strip()]
        logger.info(f"[ingest] {document_id}: {len(non_empty)}/{len(pages)} pages have content — proceeding to chunk+embed")
        if not non_empty:
            raise ValueError("All extracted pages are empty. OCR/Extraction failed to retrieve usable text.")

        # ── Chunk + Embed + Store ────────────────────────────────────────────
        update_doc({"status": "indexing"})

        from app.services.rag.store import KnowledgeStore
        store = KnowledgeStore()
        logger.info(f"[ingest] {document_id}: starting KnowledgeStore.ingest_pages")
        total_chunks = store.ingest_pages(document_id, pages, source_label=filename)
        total_pages = len(pages)

        # ── Run Knowledge Extraction Agent (Atomic Facts + Entity Suggestions) ──
        try:
            from app.agents.knowledge_extraction import extract_and_index_document_knowledge
            full_doc_text = "\n\n".join([p.get("content", "") for p in pages if p.get("content")])
            extract_res = extract_and_index_document_knowledge(
                document_id=document_id,
                document_text=full_doc_text,
                source_filename=filename
            )
            logger.info(f"[ingest] Knowledge extraction completed for {document_id}: {extract_res}")
        except Exception as k_err:
            logger.warning(f"[ingest] Knowledge extraction agent non-fatal error: {k_err}")

        if total_chunks == 0:
            raise ValueError("No text chunks were generated from the extracted text.")

        update_doc({
            "status": "indexed"
        })
        logger.info(f"[ingest] ✅ {document_id} indexed: {total_pages} pages, {total_chunks} chunks.")

    except Exception as e:
        logger.error(f"[ingest] ❌ pipeline failed for {document_id} ({filename}): {e}", exc_info=True)
        update_doc({"status": "failed", "error": str(e)})


@router.post("", response_model=StandardResponse)
async def ingest_document(payload: IngestRequest, background_tasks: BackgroundTasks):
    """Trigger ingest for a document already in Supabase storage."""
    document_id = str(uuid.uuid4())
    supa = get_supabase_client()

    storage_path = payload.storage_path or f"{document_id}/{payload.filename or 'document'}"
    filename = payload.filename or "document"

    if supa:
        try:
            supa.table("documents").insert({
                "id": document_id,
                "file_name": filename,
                "mime_type": "application/octet-stream",
                "status": "processing",
                "storage_path": storage_path
            }).execute()
        except Exception as e:
            logger.warning(f"Could not create document row: {e}")

    background_tasks.add_task(
        _run_ingest_pipeline,
        document_id=document_id,
        storage_path=storage_path,
        filename=filename
    )

    return StandardResponse(ok=True, data={"document_id": document_id})


@router.post("/upload", response_model=StandardResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """Upload a file directly, then run ingest pipeline."""
    import mimetypes

    document_id = str(uuid.uuid4())
    filename = file.filename or "upload"
    file_bytes = await file.read()
    size_bytes = len(file_bytes)
    mime = file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    storage_path = f"{document_id}/{filename}"
    supa = get_supabase_client()

    # Upload to Supabase storage
    if supa:
        try:
            supa.storage.from_("knowledge-uploads").upload(
                storage_path, file_bytes, {"content-type": mime}
            )
        except Exception as e:
            logger.warning(f"Storage upload failed: {e}")

        try:
            supa.table("documents").insert({
                "id": document_id,
                "file_name": filename,
                "mime_type": mime,
                "status": "uploading",
                "storage_path": storage_path
            }).execute()
        except Exception as e:
            logger.error(f"DB insert for document failed: {e}")

    background_tasks.add_task(
        _run_ingest_pipeline,
        document_id=document_id,
        storage_path=storage_path,
        filename=filename,
        file_bytes=file_bytes
    )

    return StandardResponse(ok=True, data={
        "document_id": document_id,
        "name": filename,
        "size_bytes": size_bytes,
        "status": "uploading",
        "storage_path": storage_path
    })
