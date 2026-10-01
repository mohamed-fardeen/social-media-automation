import io
from typing import List
from app.services.ocr.base import OCRProvider, OCRResult
from app.config.logging import logger

class TesseractOCRProvider(OCRProvider):
    def __init__(self):
        try:
            import pytesseract
            from PIL import Image
            self.pytesseract = pytesseract
            self.Image = Image
            self.available = True
        except ImportError:
            logger.warning("pytesseract or PIL not installed. Tesseract OCR disabled.")
            self.available = False

    def extract_text_from_image(self, image_bytes: bytes, filename: str = "") -> List[OCRResult]:
        if not self.available:
            return [OCRResult(text="", page_number=1, confidence=0.0, source_filename=filename)]
        
        try:
            image = self.Image.open(io.BytesIO(image_bytes))
            text = self.pytesseract.image_to_string(image)
            return [OCRResult(
                text=text.strip(),
                page_number=1,
                confidence=0.85,
                source_filename=filename
            )]
        except Exception as e:
            logger.error(f"Tesseract OCR failed on image {filename}: {e}")
            return [OCRResult(text="", page_number=1, confidence=0.0, source_filename=filename)]

    def extract_text_from_pdf_page(self, page_image_bytes: bytes, page_number: int, filename: str = "") -> List[OCRResult]:
        res = self.extract_text_from_image(page_image_bytes, filename)
        for r in res:
            r.page_number = page_number
        return res
