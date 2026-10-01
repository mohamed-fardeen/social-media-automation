from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class OCRResult(BaseModel):
    text: str
    page_number: int = 1
    confidence: float = 1.0
    bounding_box: Optional[List[float]] = None
    source_filename: str = ""

class OCRProvider(ABC):
    @abstractmethod
    def extract_text_from_image(self, image_bytes: bytes, filename: str = "") -> List[OCRResult]:
        """Extract text from raw image bytes."""
        pass

    @abstractmethod
    def extract_text_from_pdf_page(self, page_image_bytes: bytes, page_number: int, filename: str = "") -> List[OCRResult]:
        """Extract text from a rendered PDF page image."""
        pass
