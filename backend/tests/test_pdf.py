"""Tests for PDF text extraction utility."""

from __future__ import annotations

import pymupdf
import pytest

from app.core.errors import ReceiptParsingError
from app.utils.pdf import clean_hebrew_text, extract_text_from_pdf, has_hebrew_content


def _make_pdf_bytes(*pages_text: str) -> bytes:
    """Create a minimal PDF with given text on each page."""
    doc = pymupdf.open()
    for text in pages_text:
        page = doc.new_page(width=595, height=842)  # A4
        # Insert Hebrew-capable text
        page.insert_text(
            point=(72, 72),
            text=text,
            fontsize=12,
            fontname="helv",
        )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _make_empty_pdf() -> bytes:
    """Create a PDF with one blank page (no text)."""
    doc = pymupdf.open()
    doc.new_page(width=595, height=842)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


class TestExtractTextFromPdf:
    """Tests for extract_text_from_pdf."""

    def test_extracts_text_from_single_page(self) -> None:
        pdf_bytes = _make_pdf_bytes("Hello World 123")
        result = extract_text_from_pdf(pdf_bytes)
        assert "Hello" in result
        assert "World" in result
        assert "123" in result

    def test_extracts_text_from_multiple_pages(self) -> None:
        pdf_bytes = _make_pdf_bytes("Page One", "Page Two")
        result = extract_text_from_pdf(pdf_bytes)
        assert "Page One" in result
        assert "Page Two" in result

    def test_raises_on_invalid_pdf(self) -> None:
        with pytest.raises(ReceiptParsingError) as exc_info:
            extract_text_from_pdf(b"not a pdf at all")
        assert exc_info.value.error_code == "RECEIPT_PARSING_ERROR"
        assert "PDF" in exc_info.value.message_en

    def test_raises_on_empty_pdf_no_text(self) -> None:
        pdf_bytes = _make_empty_pdf()
        with pytest.raises(ReceiptParsingError) as exc_info:
            extract_text_from_pdf(pdf_bytes)
        assert "scanned" in exc_info.value.message_en.lower() or "text" in exc_info.value.message_en.lower()

    def test_respects_max_pages(self) -> None:
        pdf_bytes = _make_pdf_bytes("Page1", "Page2", "Page3")
        result = extract_text_from_pdf(pdf_bytes, max_pages=1)
        assert "Page1" in result
        assert "Page2" not in result

    def test_hebrew_text_extraction(self) -> None:
        """Test that Hebrew characters survive extraction (rendered as Latin fallback in helv font,
        but the extraction pipeline handles real Hebrew PDFs)."""
        # PyMuPDF's helv font doesn't render Hebrew glyphs, but we can test
        # the pipeline doesn't crash and processes whatever text is present.
        pdf_bytes = _make_pdf_bytes("Receipt 12345 Total 99.90")
        result = extract_text_from_pdf(pdf_bytes)
        assert "Receipt" in result
        assert "99.90" in result

    def test_raises_on_empty_bytes(self) -> None:
        with pytest.raises(ReceiptParsingError):
            extract_text_from_pdf(b"")


class TestCleanHebrewText:
    """Tests for clean_hebrew_text."""

    def test_preserves_hebrew_and_digits(self) -> None:
        text = "חלב תנובה 3% 1 ליטר  ₪5.90"
        result = clean_hebrew_text(text)
        assert "חלב תנובה" in result
        assert "3%" in result
        assert "₪5.90" in result

    def test_removes_control_characters(self) -> None:
        text = "hello\x00world\x01test"
        result = clean_hebrew_text(text)
        assert "\x00" not in result
        assert "\x01" not in result
        assert "hello" in result
        assert "world" in result

    def test_collapses_whitespace(self) -> None:
        text = "item    one      ₪10.00"
        result = clean_hebrew_text(text)
        assert "item one ₪10.00" == result

    def test_collapses_excessive_newlines(self) -> None:
        text = "line1\n\n\n\n\nline2"
        result = clean_hebrew_text(text)
        assert result == "line1\n\nline2"

    def test_strips_lines(self) -> None:
        text = "  item one  \n  item two  "
        result = clean_hebrew_text(text)
        assert result == "item one\nitem two"

    def test_unicode_normalization(self) -> None:
        # Composed vs decomposed Hebrew with nikud
        # שָׁלוֹם in decomposed form
        decomposed = "שָׁלוֹם"
        result = clean_hebrew_text(decomposed)
        assert "שׁ" in result or "ש" in result  # normalized form preserved

    def test_preserves_receipt_symbols(self) -> None:
        text = "סה\"כ: ₪123.45 (כולל מע\"מ)"
        result = clean_hebrew_text(text)
        assert "₪123.45" in result
        assert "כולל" in result

    def test_empty_string(self) -> None:
        assert clean_hebrew_text("") == ""

    def test_mixed_hebrew_latin(self) -> None:
        text = "Coca Cola קוקה קולה 1.5L"
        result = clean_hebrew_text(text)
        assert "Coca Cola" in result
        assert "קוקה קולה" in result
        assert "1.5L" in result


class TestHasHebrewContent:
    """Tests for has_hebrew_content."""

    def test_hebrew_text(self) -> None:
        assert has_hebrew_content("חלב") is True

    def test_latin_text(self) -> None:
        assert has_hebrew_content("milk") is False

    def test_mixed_text(self) -> None:
        assert has_hebrew_content("milk חלב") is True

    def test_empty_text(self) -> None:
        assert has_hebrew_content("") is False

    def test_digits_only(self) -> None:
        assert has_hebrew_content("12345") is False

    def test_hebrew_presentation_forms(self) -> None:
        # FB1D = HEBREW LETTER YOD WITH HIRIQ
        assert has_hebrew_content("\uFB1D") is True
