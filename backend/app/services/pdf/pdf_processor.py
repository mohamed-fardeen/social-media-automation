import io
from typing import List, Dict, Any, Optional
from app.services.ocr.base import OCRProvider, OCRResult
from app.services.ocr.paddle_ocr import PaddleOCRProvider
from app.services.ocr.tesseract_ocr import TesseractOCRProvider
from app.config.settings import settings
from app.config.logging import logger

def get_ocr_provider() -> OCRProvider:
    if settings.OCR_PROVIDER.lower() == "paddleocr":
        return PaddleOCRProvider()
    return TesseractOCRProvider()

class PDFProcessor:
    def __init__(self, ocr_provider: Optional[OCRProvider] = None):
        self.ocr = ocr_provider or get_ocr_provider()

    def process_pdf(self, pdf_bytes: bytes, filename: str = "") -> List[Dict[str, Any]]:
        """
        Hybrid OCR-First PDF Processing:
        1. Inspect PDF page for embedded text layer.
        2. If text layer exists and has substantial text, extract natively.
        3. If page is scanned/image-only, render page to image & OCR.
        """
        pages_content: List[Dict[str, Any]] = []
        
        # Try native extraction with pypdf / pdfplumber first
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for idx, page in enumerate(pdf.pages):
                    page_num = idx + 1
                    extracted_text = page.extract_text() or ""
                    
                    # If embedded text is sufficient (> 50 chars), use it directly
                    if len(extracted_text.strip()) > 50:
                        pages_content.append({
                            "page_number": page_num,
                            "content": extracted_text.strip(),
                            "method": "embedded_text",
                            "confidence": 1.0,
                            "filename": filename
                        })
                    else:
                        # Scanned page fallback: Render page to image & OCR
                        logger.info(f"Page {page_num} of {filename} has low/no text layer. Running OCR...")
                        ocr_res = self._ocr_pdf_page(pdf_bytes, page_num, filename)
                        pages_content.append(ocr_res)
            return pages_content
        except Exception as e:
            logger.warning(f"Native PDF extraction failed for {filename}: {e}. Falling back to page rendering + OCR.")
            return self._ocr_all_pages(pdf_bytes, filename)

    def _ocr_pdf_page(self, pdf_bytes: bytes, page_number: int, filename: str) -> Dict[str, Any]:
        try:
            import pymupdf as fitz
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            page = doc[page_number - 1]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            page_img_bytes = pix.tobytes("png")
            
            results = self.ocr.extract_text_from_pdf_page(page_img_bytes, page_number, filename)
            text = "\n".join([r.text for r in results if r.text])
            conf = results[0].confidence if results else 0.8
            
            return {
                "page_number": page_number,
                "content": text,
                "method": "ocr",
                "confidence": conf,
                "filename": filename
            }
        except Exception as e:
            logger.error(f"Failed to OCR PDF page {page_number} for {filename}: {e}")
            
        return {
            "page_number": page_number,
            "content": "",
            "method": "failed",
            "confidence": 0.0,
            "filename": filename
        }

    def _ocr_all_pages(self, pdf_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
        pages_content = []
        try:
            import pymupdf as fitz
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            for idx, page in enumerate(doc):
                page_num = idx + 1
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                page_img_bytes = pix.tobytes("png")
                results = self.ocr.extract_text_from_pdf_page(page_img_bytes, page_num, filename)
                text = "\n".join([r.text for r in results if r.text])
                pages_content.append({
                    "page_number": page_num,
                    "content": text,
                    "method": "ocr_full",
                    "confidence": 0.85,
                    "filename": filename
                })
        except Exception as e:
            logger.error(f"Failed full OCR for {filename}: {e}")
        return pages_content
