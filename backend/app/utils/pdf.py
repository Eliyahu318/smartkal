"""PDF text extraction utility with Hebrew text cleaning for receipt parsing."""

from __future__ import annotations

import re
import unicodedata

import pymupdf

from app.core.errors import ReceiptParsingError

# Hebrew Unicode range: \u0590-\u05FF (letters, vowels, cantillation)
# Hebrew presentation forms: \uFB1D-\uFB4F
_HEBREW_CHAR_RE = re.compile(r"[\u0590-\u05FF\uFB1D-\uFB4F]")

# Characters commonly found in Israeli receipts alongside Hebrew
_RECEIPT_ALLOWED_RE = re.compile(
    r"[^\u0590-\u05FF\uFB1D-\uFB4F"  # Hebrew
    r"a-zA-Z"  # Latin (brand names, units)
    r"0-9"  # Digits
    r"\s"  # Whitespace
    r".,;:!?\-+*/=%₪$€£"  # Punctuation & currency
    r"()\[\]{}<>\"'`"  # Brackets & quotes
    r"@#&_~|/\\]"  # Misc symbols
)

# Collapse multiple whitespace (but preserve newlines)
_MULTI_SPACE_RE = re.compile(r"[^\S\n]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


def extract_text_from_pdf(pdf_bytes: bytes, *, max_pages: int = 50) -> str:
    """Extract and clean text from a receipt PDF.

    Args:
        pdf_bytes: Raw PDF file bytes.
        max_pages: Safety limit on pages to process.

    Returns:
        Cleaned UTF-8 text ready for AI parsing.

    Raises:
        ReceiptParsingError: If the PDF cannot be opened or contains no text.
    """
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")  # type: ignore[no-untyped-call]
    except Exception as exc:
        raise ReceiptParsingError(
            message_he="לא ניתן לפתוח את קובץ ה-PDF",
            message_en="Failed to open PDF file",
            details={"reason": str(exc)},
        ) from exc

    if doc.page_count == 0:
        doc.close()  # type: ignore[no-untyped-call]
        raise ReceiptParsingError(
            message_he="קובץ ה-PDF ריק",
            message_en="PDF file has no pages",
        )

    pages_to_process = min(doc.page_count, max_pages)
    raw_pages: list[str] = []

    try:
        for page_num in range(pages_to_process):
            page = doc[page_num]
            # sort=True reorders text blocks top-left to bottom-right,
            # which helps with column-based receipt layouts
            text = page.get_text("text", sort=True)  # type: ignore[no-untyped-call]
            if text.strip():
                raw_pages.append(text)
    finally:
        doc.close()  # type: ignore[no-untyped-call]

    if not raw_pages:
        raise ReceiptParsingError(
            message_he="לא נמצא טקסט בקובץ ה-PDF — ייתכן שמדובר בסריקה",
            message_en="No text found in PDF — it may be a scanned image",
        )

    full_text = "\n".join(raw_pages)
    return clean_hebrew_text(full_text)


def clean_hebrew_text(text: str) -> str:
    """Clean and normalize Hebrew receipt text.

    Steps:
      1. Unicode NFC normalization
      2. Remove non-printable / control characters (keep newlines)
      3. Strip characters not expected in receipts
      4. Collapse excessive whitespace
      5. Strip leading/trailing whitespace per line
    """
    # 1. Normalize unicode (compose characters)
    text = unicodedata.normalize("NFC", text)

    # 2. Remove control chars except newline and tab
    text = "".join(
        ch for ch in text if ch in ("\n", "\t") or not unicodedata.category(ch).startswith("C")
    )

    # 3. Remove unexpected characters
    text = _RECEIPT_ALLOWED_RE.sub("", text)

    # 4. Collapse whitespace
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)

    # 5. Strip each line
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(lines)

    return text.strip()


def has_hebrew_content(text: str) -> bool:
    """Check if text contains any Hebrew characters."""
    return bool(_HEBREW_CHAR_RE.search(text))
