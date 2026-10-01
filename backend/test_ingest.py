import time
import io
from app.services.pdf.pdf_processor import PDFProcessor
from app.services.rag.store import KnowledgeStore
from app.database.supabase_client import get_supabase_client

def test():
    print("Reading PDF file...")
    with open("C:/Users/Abdullah/Downloads/Autonomous_3D_Architecture.pdf", "rb") as f:
        pdf_bytes = f.read()

    print(f"File read complete. Size: {len(pdf_bytes)} bytes.")

    processor = PDFProcessor()
    print("Processing PDF...")
    start_time = time.time()
    pages = processor.process_pdf(pdf_bytes, "Autonomous_3D_Architecture.pdf")
    processing_time = time.time() - start_time
    print(f"PDF processed in {processing_time:.2f}s. Extracted {len(pages)} pages.")

    total_chars = 0
    pages_with_content = 0
    for p in pages:
        text_len = len(p.get("content", ""))
        total_chars += text_len
        if text_len > 0:
            pages_with_content += 1
        print(f"Page {p['page_number']}: method={p['method']}, chars={text_len}, confidence={p['confidence']}")

    print(f"Total characters: {total_chars}")
    print(f"Pages with text content: {pages_with_content} / {len(pages)}")

    if pages_with_content == 0:
        print("Extraction failed: no text extracted from pages.")
        return

    print("Running KnowledgeStore ingestion (chunking, embedding, Supabase insert)...")
    store = KnowledgeStore()
    # Use integer or uuid format since id in documents is text/varchar
    doc_id = "00000000-0000-0000-0000-000000000123"
    
    # Create the document row first to satisfy foreign key constraints
    supa = get_supabase_client()
    if supa:
        try:
            supa.table("documents").delete().eq("id", doc_id).execute()
        except Exception:
            pass
        supa.table("documents").insert({
            "id": doc_id,
            "file_name": "Autonomous_3D_Architecture.pdf",
            "mime_type": "application/pdf",
            "status": "processing",
            "storage_path": "test/Autonomous_3D_Architecture.pdf"
        }).execute()
        print("Document row created in Supabase.")

    start_ingest = time.time()
    total_chunks = store.ingest_pages(doc_id, pages, source_label="Autonomous_3D_Architecture.pdf")
    ingest_time = time.time() - start_ingest
    print(f"Ingestion complete in {ingest_time:.2f}s. Generated {total_chunks} chunks.")

    if supa:
        supa.table("documents").update({"status": "indexed"}).eq("id", doc_id).execute()
        print("Document status updated to indexed.")

if __name__ == "__main__":
    test()
