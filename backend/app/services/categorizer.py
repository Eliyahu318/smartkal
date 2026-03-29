"""Auto-categorization service using Claude API for Hebrew product names."""

from __future__ import annotations

import json
import uuid

import structlog
from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import ClaudeAPIError
from app.models.category import Category

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


async def auto_categorize(
    db: AsyncSession,
    user_id: uuid.UUID,
    product_name: str,
) -> uuid.UUID | None:
    """Use Claude to categorize a Hebrew product name into one of the user's categories.

    Returns the category_id if successful, None if categorization fails or API is unavailable.
    """
    settings = get_settings()

    if not settings.anthropic_api_key:
        await logger.awarning("auto_categorize_skipped", reason="no_api_key")
        return None

    # Fetch user's categories
    result = await db.execute(
        select(Category)
        .where(Category.user_id == user_id)
        .order_by(Category.display_order)
    )
    categories = result.scalars().all()

    if not categories:
        return None

    category_names = [c.name for c in categories]
    category_map = {c.name: c.id for c in categories}

    prompt = (
        f"סווג את המוצר הבא לאחת מהקטגוריות.\n"
        f"מוצר: {product_name}\n"
        f"קטגוריות: {', '.join(category_names)}\n\n"
        f'החזר JSON בלבד בפורמט: {{"category": "שם הקטגוריה"}}\n'
        f"אם לא ניתן לסווג, החזר: {{\"category\": \"אחר\"}}"
    )

    try:
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract text from response
        first_block = response.content[0]
        text: str = first_block.text.strip()  # type: ignore[union-attr]

        # Parse JSON response
        parsed = json.loads(text)
        category_name = parsed.get("category", "")

        if category_name in category_map:
            await logger.ainfo(
                "auto_categorized",
                product=product_name,
                category=category_name,
            )
            return category_map[category_name]

        # Try partial match (category name contains or is contained in response)
        for name, cat_id in category_map.items():
            if name in category_name or category_name in name:
                await logger.ainfo(
                    "auto_categorized_partial",
                    product=product_name,
                    category=name,
                )
                return cat_id

        await logger.awarning(
            "auto_categorize_no_match",
            product=product_name,
            claude_response=category_name,
        )
        return None

    except json.JSONDecodeError:
        await logger.awarning(
            "auto_categorize_json_error",
            product=product_name,
        )
        return None
    except Exception as exc:
        await logger.aerror(
            "auto_categorize_failed",
            product=product_name,
            error=str(exc),
        )
        return None
