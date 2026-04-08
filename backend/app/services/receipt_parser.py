"""Claude AI receipt parser service for extracting structured data from receipt text."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

import structlog
from anthropic import AsyncAnthropic

from app.config import get_settings
from app.core.errors import ClaudeAPIError, ReceiptParsingError

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

SYSTEM_PROMPT = """\
אתה מנתח קבלות סופרמרקט ישראליות מדויק ומהיר.
תפקידך: לחלץ נתוני מוצרים מטקסט קבלה ולהחזיר JSON תקין בלבד.
אתה מחזיר אך ורק JSON — בלי markdown, בלי הסברים, בלי backticks."""

RECEIPT_PARSE_PROMPT = """\
חלץ את כל המוצרים מהקבלה הבאה והחזר JSON בפורמט הזה בדיוק:

{"store_name":"שם הרשת","store_branch":"סניף או null","receipt_date":"YYYY-MM-DD או null","total_amount":123.45,"items":[{"name":"שם מוצר","canonical_name":"שם קנוני","quantity":1.0,"unit_price":12.90,"total_price":12.90,"barcode":"ברקוד או null"}]}

כללים:
- JSON בלבד. בלי ```json, בלי הסברים, בלי טקסט נוסף
- שמות מוצרים בעברית כפי שמופיעים בקבלה (שדה name)
- canonical_name = השם הבסיסי של הפריט בלי מותג, בלי גודל/משקל, בלי מילים שיווקיות (פרימיום, מובחר, קלאסי), ובלי תיאורי וריאציה (עגול, ארוך, חתוך). דוגמאות: "עגבניות שרי פרימיום תנובה 250 גרם" → canonical_name: "עגבניות שרי". "חלב תנובה 3% 1 ליטר" → canonical_name: "חלב 3%".
- חשוב מאוד: אסור להסיר מ-canonical_name מאפיינים שמשנים את המהות של המוצר: אחוזי שומן (1%, 3%, 5%), טעמים (וניל, שוקולד, תות), מילים כמו "לייט", "דל שומן", "זירו", "ללא סוכר", סוגי חלב צמחי (סויה, שקדים, שיבולת שועל). דוגמה: "קוקה קולה זירו" צריך להישאר "קוקה קולה זירו", לא "קוקה קולה".
- מחירים כמספרים (לא מחרוזות)
- כמות ברירת מחדל: 1.0
- התעלם משורות שאינן מוצרים (כותרות, סיכומים, מע"מ, תשלום, ברקודים בודדים)
- שדה חסר = null

טקסט הקבלה:
"""

RETRY_PROMPT = """\
ה-JSON שהחזרת לא תקין. השגיאה: {error}

חזור על הניתוח והחזר JSON תקין בלבד. בלי markdown, בלי backticks, בלי הסברים.
רק JSON חוקי שמתחיל ב-{{ ומסתיים ב-}}."""

MAX_RETRIES = 2
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 16384


@dataclass
class ParsedItem:
    """A single parsed item from a receipt."""

    name: str
    quantity: float
    unit_price: Decimal | None
    total_price: Decimal | None
    barcode: str | None
    canonical_name: str | None = None


@dataclass
class ParsedReceipt:
    """Structured data extracted from a receipt by Claude."""

    store_name: str | None
    store_branch: str | None
    receipt_date: str | None
    total_amount: Decimal | None
    items: list[ParsedItem] = field(default_factory=list)
    raw_json: dict[str, object] = field(default_factory=dict)


def _safe_decimal(value: object) -> Decimal | None:
    """Convert a value to Decimal, returning None on failure."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _validate_and_build(data: dict[str, object]) -> ParsedReceipt:
    """Validate Claude's JSON response and build a ParsedReceipt.

    Raises ReceiptParsingError if the response structure is invalid.
    """
    if not isinstance(data, dict):
        raise ReceiptParsingError(
            message_he="תגובת Claude אינה בפורמט תקין",
            message_en="Claude response is not a valid object",
        )

    raw_items = data.get("items")
    if not isinstance(raw_items, list):
        raise ReceiptParsingError(
            message_he="תגובת Claude לא כוללת רשימת מוצרים",
            message_en="Claude response missing items array",
        )

    items: list[ParsedItem] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        name = raw.get("name")
        if not name or not isinstance(name, str) or not name.strip():
            continue

        canonical_raw = raw.get("canonical_name")
        canonical_name: str | None = None
        if isinstance(canonical_raw, str) and canonical_raw.strip():
            canonical_name = canonical_raw.strip()

        items.append(
            ParsedItem(
                name=name.strip(),
                quantity=float(raw.get("quantity", 1.0) or 1.0),
                unit_price=_safe_decimal(raw.get("unit_price")),
                total_price=_safe_decimal(raw.get("total_price")),
                barcode=str(raw["barcode"]).strip() if raw.get("barcode") else None,
                canonical_name=canonical_name,
            )
        )

    store_name = data.get("store_name")
    store_branch = data.get("store_branch")
    receipt_date = data.get("receipt_date")

    return ParsedReceipt(
        store_name=str(store_name).strip() if store_name else None,
        store_branch=str(store_branch).strip() if store_branch else None,
        receipt_date=str(receipt_date).strip() if receipt_date else None,
        total_amount=_safe_decimal(data.get("total_amount")),
        items=items,
        raw_json=data,
    )


async def parse_receipt(receipt_text: str) -> ParsedReceipt:
    """Parse receipt text using Claude Sonnet and return structured data.

    Retries up to MAX_RETRIES times on failure.

    Raises:
        ReceiptParsingError: If the receipt text is empty or Claude returns invalid data.
        ClaudeAPIError: If the Claude API is unavailable or fails after retries.
    """
    if not receipt_text or not receipt_text.strip():
        raise ReceiptParsingError(
            message_he="טקסט הקבלה ריק",
            message_en="Receipt text is empty",
        )

    settings = get_settings()
    if not settings.anthropic_api_key:
        raise ClaudeAPIError(
            message_he="מפתח API של Claude לא הוגדר",
            message_en="Claude API key not configured",
        )

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    user_prompt = RECEIPT_PARSE_PROMPT + receipt_text

    # Build conversation — retries append error feedback so Claude can self-correct
    messages: list[dict[str, str]] = [{"role": "user", "content": user_prompt}]

    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 2):  # 1 initial + MAX_RETRIES retries
        try:
            response = await client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=messages,
            )

            first_block = response.content[0]
            text: str = first_block.text.strip()  # type: ignore[union-attr]

            # Strip markdown code fences if present
            if text.startswith("```"):
                start_idx = text.find("\n")
                if start_idx == -1:
                    start_idx = 3
                else:
                    start_idx += 1
                end_idx = text.rfind("```")
                if end_idx > start_idx:
                    text = text[start_idx:end_idx].strip()
                else:
                    text = text[start_idx:].strip()

            # Check if response was truncated (hit max_tokens)
            if response.stop_reason == "max_tokens":
                raise ReceiptParsingError(
                    message_he="תגובת Claude נחתכה באמצע — הקבלה ארוכה מדי",
                    message_en="Claude response truncated (max_tokens reached)",
                )

            data = json.loads(text)
            parsed = _validate_and_build(data)

            await logger.ainfo(
                "receipt_parsed",
                attempt=attempt,
                store=parsed.store_name,
                item_count=len(parsed.items),
                total=str(parsed.total_amount),
            )
            return parsed

        except (ReceiptParsingError, json.JSONDecodeError) as exc:
            last_error = exc
            await logger.awarning(
                "receipt_parse_attempt_failed",
                attempt=attempt,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            if attempt >= MAX_RETRIES + 1:
                break
            # Append Claude's broken response + error feedback for self-correction
            messages.append({"role": "assistant", "content": text if "text" in dir() else ""})
            messages.append({
                "role": "user",
                "content": RETRY_PROMPT.format(error=str(exc)),
            })

        except Exception as exc:
            last_error = exc
            await logger.aerror(
                "claude_api_error",
                attempt=attempt,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            if attempt >= MAX_RETRIES + 1:
                break
            # On API errors, reset conversation and retry fresh
            messages = [{"role": "user", "content": user_prompt}]

    # All attempts exhausted
    if isinstance(last_error, (ReceiptParsingError, json.JSONDecodeError)):
        raise ReceiptParsingError(
            message_he="לא ניתן לפענח את תגובת Claude לאחר מספר ניסיונות",
            message_en=f"Failed to parse Claude response after {MAX_RETRIES + 1} attempts",
            details={"last_error": str(last_error)},
        )
    raise ClaudeAPIError(
        message_he="שגיאה בתקשורת עם Claude לאחר מספר ניסיונות",
        message_en=f"Claude API failed after {MAX_RETRIES + 1} attempts",
        details={"last_error": str(last_error)},
    )
