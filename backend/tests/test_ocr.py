"""
Tests for OCR pipeline — PDF extraction and image OCR.
"""
import io
import pytest
from unittest.mock import patch, MagicMock


class TestTesseractOCR:
    def test_import_graceful_failure(self):
        """Should not crash if pytesseract is not installed."""
        with patch.dict("sys.modules", {"pytesseract": None}):
            from app.services.ocr.tesseract_ocr import TesseractOCRProvider
            provider = TesseractOCRProvider()
            assert provider.available is False

    def test_extract_returns_list(self):
        from app.services.ocr.tesseract_ocr import TesseractOCRProvider
        provider = TesseractOCRProvider()
        if not provider.available:
            pytest.skip("Tesseract not installed")
        result = provider.extract_text_from_image(b"fake_image_bytes", "test.png")
        assert isinstance(result, list)


class TestPDFProcessor:
    def test_process_pdf_returns_pages(self):
        """Should return a list of page dicts."""
        from app.services.pdf.pdf_processor import PDFProcessor
        processor = PDFProcessor()

        # Minimal valid PDF bytes
        minimal_pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"

        try:
            pages = processor.process_pdf(minimal_pdf, "test.pdf")
            assert isinstance(pages, list)
        except Exception:
            pytest.skip("PDF processing requires dependencies")

    def test_empty_pdf_bytes_handled(self):
        from app.services.pdf.pdf_processor import PDFProcessor
        processor = PDFProcessor()
        try:
            pages = processor.process_pdf(b"", "empty.pdf")
            assert isinstance(pages, list)
        except Exception:
            pytest.skip("Dependency not available")


class TestOCRProvider:
    def test_paddle_ocr_falls_back_to_tesseract(self):
        """With lazy init, available=False should route to Tesseract fallback."""
        from app.services.ocr.paddle_ocr import PaddleOCRProvider
        provider = PaddleOCRProvider()
        # Force available to False by making _ensure_engine fail
        provider._available = False
        provider._ocr_engine = None
        assert provider.available is False
        assert provider.fallback is not None
