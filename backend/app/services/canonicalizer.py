"""Canonical name extraction for Hebrew grocery products.

The dedup pipeline needs a "canonical key" — a short, brand-free, size-free, variant-free
form of a product name — so that variants printed on different receipts
("עגבניות שרי", "עגבניות שרי פרימיום", "עגבניות שרי עגול") collapse to the same key
on a per-user list. This module provides:

1. canonical_key(): a deterministic, pure function that strips known stopwords
   (brands, quality markers, shape variants, size units) from a Hebrew product name.
   No API calls. Fast and testable.

2. extract_canonical_names_claude(): a batched Claude fallback for backfilling old
   products that were created before the parser started emitting canonical_name.
   Used only by the dedup_backfill service, never in the request path.

CRITICAL: The canonicalizer must NEVER merge meaningfully different products.
The stopword lists are intentionally narrow. Anything that could distinguish a SKU
that a shopper would care about (fat percentage, flavor, diet marker, milk source)
is preserved. See test_canonicalizer.py for the parametrized negative cases.
"""

from __future__ import annotations

import asyncio
import json
import os
import re

import anthropic
import structlog

from app.services.product_matcher import normalize_hebrew_name

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


# --- Stopword lists -----------------------------------------------------------

# Israeli supermarket brand names. Removed from product names because two SKUs
# of "עגבניות שרי" from תנובה vs רמי לוי are conceptually the same item on a
# shopping list, even if they're separate global Products for price tracking.
BRAND_WORDS: frozenset[str] = frozenset(
    {
        "תנובה",
        "שטראוס",
        "עלית",
        "אסם",
        "יוטבתה",
        "טרה",
        "נסטלה",
        "מחלבות",
        "תלמה",
        "יד מרדכי",
        "בייגל בייגל",
        "ויסוצקי",
        "וויסוצקי",
        "סנפרוסט",
        "סופרסל",
        "רמי לוי",
        "שופרסל",
        "ויקטורי",
        "מאסטר שף",
        "סוגת",
        "פרי הגליל",
        "סלטי צבר",
        "אחלה",
        "מאמא עוף",
        "עוף טוב",
        "זוגלובק",
        "תפוגן",
        "כרמל",
        "ברקן",
        "טמפו",
        "פרנו",
        "מילקה",
        "קלוג'ס",
        "קלוגס",
    }
)

# Marketing / quality descriptors. Customers don't usually distinguish "פרימיום"
# from regular when planning their shopping list — they want "the thing".
QUALITY_WORDS: frozenset[str] = frozenset(
    {
        "פרימיום",
        "מובחר",
        "משובח",
        "קלאסי",
        "מהדורה",
        "מיוחד",
        "מיוחדת",
        "איכות",
        "איכותי",
        "אורגני",  # debatable — but most shoppers treat as a list-level distinction; keep for now
        "טבעי",
        "ביתי",
        "אותנטי",
        "מסורתי",
        "חדש",
    }
)

# Shape / form / size adjectives that don't change what the item IS.
# "עגבניות שרי עגול" vs "עגבניות שרי" → same shopping list entry.
SHAPE_WORDS: frozenset[str] = frozenset(
    {
        "עגול",
        "עגולה",
        "עגולות",
        "ארוך",
        "ארוכה",
        "ארוכות",
        "חתוך",
        "חתוכה",
        "חתוכות",
        "שלם",
        "שלמה",
        "שלמות",
        "מגורד",
        "מגורדת",
        "פרוס",
        "פרוסה",
        "פרוסות",
        "פרוסים",
        "קטן",
        "קטנה",
        "קטנים",
        "קטנות",
        "גדול",
        "גדולה",
        "גדולים",
        "גדולות",
        "בינוני",
        "בינונית",
        "ענק",
        "מיני",
        "טרי",
        "טרייה",
        "טריה",
        "טריים",
        "טריות",
        "קפוא",
        "קפואה",
        "קפואים",
        "קפואות",
    }
)

# Packaging words.
PACKAGING_WORDS: frozenset[str] = frozenset(
    {
        "אריזה",
        "באריזה",
        "מארז",
        "במארז",
        "חבילה",
        "בחבילה",
        "שקית",
        "בשקית",
        "קרטון",
        "בקרטון",
        "קופסה",
        "בקופסה",
        "בקבוק",
        "בבקבוק",
        "פחית",
        "בפחית",
    }
)

ALL_STOPWORDS: frozenset[str] = BRAND_WORDS | QUALITY_WORDS | SHAPE_WORDS | PACKAGING_WORDS


# Size / unit pattern: digits (with optional decimal) followed by a Hebrew unit.
# Catches "250 גרם", "1.5 ליטר", "500 מ\"ל", "12 יח", "2 ק\"ג", "500ג", "1ליטר" etc.
# IMPORTANT: this pattern intentionally requires at least one digit immediately
# before the unit, so it never matches a bare unit word that could be part of
# something else.
SIZE_UNIT_PATTERN = re.compile(
    r"\d+(?:[.,]\d+)?\s*"
    r'(?:גרם|ג"ר|גר\'?|ג(?=\b|\s)'
    r'|ק"ג|קג|ק\'?ג|קילו|קילוגרם'
    r'|ליטר|ל"|ל\'|לי(?=\b|\s)'
    r'|מ"ל|מל|מיליליטר'
    r"|יחידות|יח'?|יח(?=\b|\s)"
    r"|אונקיות|אונקיה"
    r")",
    re.IGNORECASE,
)

# Bare digit-only tokens at word boundaries (e.g., "1", "2") — but ONLY if
# followed by what looks like quantity context. We do NOT strip standalone
# digits because "3%" must be preserved.
# This is handled by SIZE_UNIT_PATTERN above + we leave anything that doesn't
# match alone.

# Strip nothing else: percentages (\d+%), flavors, diet markers, milk types
# are all preserved by default since they are not in any stopword list.


def _strip_words(text: str, stopwords: frozenset[str]) -> str:
    """Remove whole-word matches against the stopword set.

    Uses Python set lookups on whitespace-tokenized words rather than regex
    alternation, which is both faster and avoids regex catastrophic backtracking
    on large stopword sets.
    """
    if not text:
        return text
    tokens = text.split()
    kept = [t for t in tokens if t not in stopwords]
    return " ".join(kept)


def canonical_key(raw: str) -> str:
    """Compute a deterministic canonical key for a Hebrew product name.

    Pipeline:
      1. strip "<digits><unit>" size tokens from the RAW input (quotes intact)
         — we have to do this BEFORE normalize_hebrew_name because Hebrew unit
         abbreviations like ק"ג, ל", מ"ל depend on the quote character that
         normalize_hebrew_name would otherwise strip.
      2. normalize_hebrew_name (NFC, strip nikud, lowercase Latin, strip punctuation)
      3. tokenize on whitespace and drop any token that is in the union of:
         brand / quality / shape / packaging stopword sets
      4. collapse whitespace

    If the result is empty (everything was stopword-stripped) or shorter than 2
    characters, the function falls back to the normalized name to avoid creating
    a key that would over-merge unrelated items.

    The function is intentionally PURE — no IO, no side effects — so it can be
    unit-tested exhaustively.
    """
    if not raw or not raw.strip():
        return ""

    # 1. strip "<digits><unit>" size tokens from raw input (quotes still intact)
    without_sizes_raw = SIZE_UNIT_PATTERN.sub(" ", raw)

    # 2. base normalization (reuses the existing helper)
    normalized = normalize_hebrew_name(without_sizes_raw)

    # 3. drop stopword tokens (brands, quality, shape, packaging)
    stripped = _strip_words(normalized, ALL_STOPWORDS)

    # 4. collapse whitespace
    stripped = re.sub(r"\s+", " ", stripped).strip()

    # Fallback: if we stripped everything (or almost everything), the canonical
    # key is too aggressive and would over-merge. Return the normalized name
    # without stopword stripping so the caller still gets *something* deterministic
    # but doesn't accidentally collapse unrelated items.
    if len(stripped) < 2:
        return normalize_hebrew_name(raw)

    return stripped


# --- Claude batched fallback (used by dedup_backfill only) -------------------

_CLAUDE_SEMAPHORE = asyncio.Semaphore(4)
_CLAUDE_MODEL = "claude-haiku-4-5-20251001"
_CLAUDE_BATCH_SIZE = 20

_CANONICAL_BATCH_SYSTEM_PROMPT = """\
אתה מומחה לקטלוג מוצרי מזון בעברית. תפקידך: עבור רשימת שמות מוצרים
מקבלות סופרמרקט, להחזיר עבור כל מוצר שם קנוני קצר.

כלל:
- שם קנוני = שם הפריט בלי מותג, בלי גודל/משקל, בלי מילים שיווקיות
  (פרימיום/מובחר/קלאסי), ובלי תיאורי וריאציה (עגול/ארוך/חתוך).
- אסור להסיר מאפיינים שמשנים את המהות: אחוזי שומן (1%, 3%, 5%),
  טעמים (וניל, שוקולד, תות), מילים כמו "לייט", "דל שומן", "זירו",
  "ללא סוכר", סוגי חלב צמחי (סויה, שקדים, שיבולת שועל).
- דוגמאות:
  "עגבניות שרי פרימיום תנובה 250 גרם" → "עגבניות שרי"
  "חלב תנובה 3% 1 ליטר" → "חלב 3%"
  "קוקה קולה זירו 1.5 ליטר" → "קוקה קולה זירו"

החזר אך ורק JSON בפורמט: {"items": ["שם קנוני 1", "שם קנוני 2", ...]}
עם בדיוק אותו מספר פריטים כפי שקיבלת ובאותו סדר.
"""


async def _call_claude_for_batch(raw_names: list[str]) -> list[str | None]:
    """Call Claude once for a single batch (up to _CLAUDE_BATCH_SIZE names)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        await logger.awarning(
            "canonicalizer_claude_skipped_no_api_key",
            count=len(raw_names),
        )
        return [None] * len(raw_names)

    client = anthropic.AsyncAnthropic(api_key=api_key)
    user_message = json.dumps({"items": raw_names}, ensure_ascii=False)

    async with _CLAUDE_SEMAPHORE:
        try:
            response = await client.messages.create(
                model=_CLAUDE_MODEL,
                max_tokens=2048,
                system=_CANONICAL_BATCH_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
        except anthropic.APIError as exc:
            await logger.aerror(
                "canonicalizer_claude_api_error",
                error=str(exc),
                count=len(raw_names),
            )
            return [None] * len(raw_names)

    # Extract text from response
    text_parts: list[str] = []
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
    text = "".join(text_parts).strip()

    # Strip markdown fences if Claude added them despite instructions
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        await logger.aerror(
            "canonicalizer_claude_invalid_json",
            error=str(exc),
            response_text=text[:500],
        )
        return [None] * len(raw_names)

    items = parsed.get("items")
    if not isinstance(items, list) or len(items) != len(raw_names):
        await logger.aerror(
            "canonicalizer_claude_shape_mismatch",
            expected=len(raw_names),
            got=len(items) if isinstance(items, list) else None,
        )
        return [None] * len(raw_names)

    result: list[str | None] = []
    for item in items:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
        else:
            result.append(None)
    return result


async def extract_canonical_names_claude(
    raw_names: list[str],
) -> list[str | None]:
    """Extract canonical names for a list of raw product names via Claude (batched).

    Returns a list of the same length as `raw_names`. Each entry is either the
    Claude-extracted canonical name, or None if Claude failed for that item or
    the entire batch (caller should fall back to canonical_key()).

    Used only by the dedup_backfill service for legacy products. Never in the
    request path. Concurrency is limited by an internal semaphore.
    """
    if not raw_names:
        return []

    results: list[str | None] = []
    for i in range(0, len(raw_names), _CLAUDE_BATCH_SIZE):
        batch = raw_names[i : i + _CLAUDE_BATCH_SIZE]
        batch_result = await _call_claude_for_batch(batch)
        results.extend(batch_result)

    return results
