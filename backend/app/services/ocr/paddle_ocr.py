import io
from typing import List, Optional
from app.services.ocr.base import OCRProvider, OCRResult
from app.config.logging import logger


class PaddleOCRProvider(OCRProvider):
    """
    OCR provider using RapidOCR (ONNX Runtime backend).

    This uses the same PaddleOCR detection/recognition models as paddleocr,
    but runs through ONNX Runtime instead of PaddlePaddle — which means it
    works on Python 3.14 and any platform without PaddlePaddle binaries.
    The OCR quality and model architecture are identical to paddleocr.
    """

    def __init__(self):
        self._ocr_engine = None
        self._available: Optional[bool] = None
        from app.services.ocr.tesseract_ocr import TesseractOCRProvider
        self.fallback = TesseractOCRProvider()

    @property
    def available(self) -> bool:
        if self._available is None:
            self._ensure_engine()
        return self._available or False

    def _ensure_engine(self):
        """Lazily initialize RapidOCR on first use."""
        if self._available is not None:
            return
        try:
            from rapidocr_onnxruntime import RapidOCR
            self._ocr_engine = RapidOCR()
            self._available = True
            logger.info("RapidOCR (ONNX Runtime) engine initialized successfully.")
        except Exception as e:
            logger.error(f"RapidOCR failed to initialize: {e}")
            self._available = False

    def extract_text_from_image(self, image_bytes: bytes, filename: str = "") -> List[OCRResult]:
        if not self.available:
            return self.fallback.extract_text_from_image(image_bytes, filename)
        self._ensure_engine()
        try:
            import numpy as np
            from PIL import Image
            img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            img_np = np.array(img)

            result, elapse = self._ocr_engine(img_np)

            ocr_results: List[OCRResult] = []
            if result:
                lines = []
                total_conf = 0.0
                count = 0
                for item in result:
                    # RapidOCR returns: [bbox, text, confidence]
                    if len(item) >= 3:
                        text = item[1]
                        conf = float(item[2]) if item[2] is not None else 0.9
                    elif len(item) >= 2:
                        text = item[1]
                        conf = 0.9
                    else:
                        continue
                    lines.append(text)
                    total_conf += conf
                    count += 1

                combined_text = "\n".join(lines)
                avg_conf = (total_conf / count) if count > 0 else 0.9

                ocr_results.append(OCRResult(
                    text=combined_text,
                    page_number=1,
                    confidence=float(avg_conf),
                    source_filename=filename
                ))
            else:
                ocr_results.append(OCRResult(text="", page_number=1, confidence=0.0, source_filename=filename))

            return ocr_results
        except Exception as e:
            logger.error(f"RapidOCR processing error for {filename}: {e}")
            return self.fallback.extract_text_from_image(image_bytes, filename)

    def extract_text_from_pdf_page(self, page_image_bytes: bytes, page_number: int, filename: str = "") -> List[OCRResult]:
        results = self.extract_text_from_image(page_image_bytes, filename)
        for r in results:
            r.page_number = page_number
        return results
