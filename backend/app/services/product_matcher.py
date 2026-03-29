"""Product matching service: matches receipt purchases to existing products.

Uses a priority chain:
1. Barcode exact match
2. Normalized name exact match
3. Fuzzy Hebrew match (rapidfuzz, threshold 0.85)
4. Create new product if no match found

When a purchase matches a list item, that item is marked as completed (just bought).
"""

from __future__ import annotations

import re
import unicodedata
import uuid

import structlog
from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.list_item import ListItem, ListItemSource, ListItemStatus
from app.models.product import Product
from app.models.receipt import Purchase, Receipt
from app.services.refresh_engine import calculate_refresh_for_item

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

FUZZY_THRESHOLD = 85.0


def normalize_hebrew_name(name: str) -> str:
    """Normalize a Hebrew product name for comparison.

    Strips nikud (vowel marks), normalizes Unicode, lowercases,
    collapses whitespace, and removes punctuation.
    """
    # Unicode NFC normalization
    text = unicodedata.normalize("NFC", name)

    # Remove Hebrew nikud (U+0591-U+05BD, U+05BF, U+05C1-U+05C2, U+05C4-U+05C7)
    text = re.sub(r"[\u0591-\u05BD\u05BF\u05C1\u05C2\u05C4-\u05C7]", "", text)

    # Lowercase (for any Latin characters mixed in)
    text = text.lower()

    # Remove common punctuation but keep digits and currency
    text = re.sub(r"[\"'\-.,;:!?()[\]{}/\\]", " ", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


async def _match_by_barcode(
    db: AsyncSession,
    barcode: str,
) -> Product | None:
    """Try to find a product by exact barcode match."""
    result = await db.execute(
        select(Product).where(Product.barcode == barcode).limit(1)
    )
    return result.scalar_one_or_none()


async def _match_by_normalized_name(
    db: AsyncSession,
    normalized_name: str,
) -> Product | None:
    """Try to find a product by exact normalized name match."""
    result = await db.execute(
        select(Product).where(Product.normalized_name == normalized_name).limit(1)
    )
    return result.scalar_one_or_none()


async def _match_by_fuzzy(
    db: AsyncSession,
    normalized_name: str,
    threshold: float = FUZZY_THRESHOLD,
) -> Product | None:
    """Try to find a product by fuzzy Hebrew name matching.

    Uses token_sort_ratio which handles word reordering well for Hebrew product names
    (e.g., "חלב תנובה 3%" vs "תנובה חלב 3%").
    """
    # Fetch all products — in a production system with many products,
    # this would use an index or pre-filtered candidate set.
    result = await db.execute(select(Product))
    products = list(result.scalars().all())

    best_match: Product | None = None
    best_score: float = 0.0

    for product in products:
        score = fuzz.token_sort_ratio(normalized_name, product.normalized_name)
        if score >= threshold and score > best_score:
            best_score = score
            best_match = product

    if best_match is not None:
        await logger.ainfo(
            "fuzzy_match_found",
            query=normalized_name,
            matched=best_match.normalized_name,
            score=best_score,
        )

    return best_match


async def match_purchase_to_product(
    db: AsyncSession,
    purchase: Purchase,
) -> tuple[Product, str]:
    """Match a single purchase to a product using the priority chain.

    Returns (product, match_type) where match_type is one of:
    'barcode', 'exact_name', 'fuzzy', 'new'.
    """
    normalized_name = normalize_hebrew_name(purchase.raw_name)

    # 1. Barcode exact match
    if purchase.barcode:
        product = await _match_by_barcode(db, purchase.barcode)
        if product is not None:
            return product, "barcode"

    # 2. Normalized name exact match
    product = await _match_by_normalized_name(db, normalized_name)
    if product is not None:
        return product, "exact_name"

    # 3. Fuzzy match
    product = await _match_by_fuzzy(db, normalized_name)
    if product is not None:
        return product, "fuzzy"

    # 4. Create new product
    product = Product(
        name=purchase.raw_name,
        normalized_name=normalized_name,
        barcode=purchase.barcode,
    )
    db.add(product)
    await db.flush()

    await logger.ainfo(
        "new_product_created",
        product_id=str(product.id),
        name=purchase.raw_name,
    )

    return product, "new"


async def _get_default_category_id(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> uuid.UUID | None:
    """Get the 'אחר' category ID for the user, or None."""
    from app.models.category import Category

    result = await db.execute(
        select(Category.id).where(
            Category.user_id == user_id,
            Category.name == "אחר",
        ).limit(1)
    )
    return result.scalar_one_or_none()


async def _complete_matching_list_items(
    db: AsyncSession,
    user_id: uuid.UUID,
    product: Product,
    purchase_quantity: float = 1.0,
) -> list[ListItem]:
    """Find active list items matching the product and mark them as completed.

    If no matching list item exists, creates a new one as completed
    so the app learns purchase patterns for future refresh predictions.

    Returns list of completed items.
    """
    from datetime import datetime, timezone

    result = await db.execute(
        select(ListItem).where(
            ListItem.user_id == user_id,
            ListItem.status == ListItemStatus.ACTIVE.value,
            ListItem.product_id == product.id,
        )
    )
    matching_items = list(result.scalars().all())

    # Also try matching by name if no product_id link exists
    if not matching_items:
        normalized = normalize_hebrew_name(product.name)
        result = await db.execute(
            select(ListItem).where(
                ListItem.user_id == user_id,
                ListItem.status == ListItemStatus.ACTIVE.value,
                ListItem.product_id.is_(None),
            )
        )
        unlinked_items = list(result.scalars().all())
        for item in unlinked_items:
            item_normalized = normalize_hebrew_name(item.name)
            score = fuzz.token_sort_ratio(normalized, item_normalized)
            if score >= FUZZY_THRESHOLD:
                # Link the item to the product
                item.product_id = product.id
                matching_items.append(item)

    now = datetime.now(timezone.utc)

    # If no existing list item found, check if a completed one already exists
    # (from a previous receipt). If not, create a new one.
    if not matching_items:
        result = await db.execute(
            select(ListItem).where(
                ListItem.user_id == user_id,
                ListItem.product_id == product.id,
            ).limit(1)
        )
        existing_completed = result.scalar_one_or_none()

        if existing_completed is None:
            default_category_id = await _get_default_category_id(db, user_id)
            new_item = ListItem(
                user_id=user_id,
                product_id=product.id,
                category_id=product.category_id or default_category_id,
                name=product.name,
                quantity=str(purchase_quantity) if purchase_quantity != 1.0 else None,
                status=ListItemStatus.COMPLETED.value,
                source=ListItemSource.RECEIPT.value,
                last_completed_at=now,
            )
            db.add(new_item)
            matching_items.append(new_item)
        else:
            # Update the existing completed item's timestamp
            existing_completed.last_completed_at = now
            matching_items.append(existing_completed)

    completed_items: list[ListItem] = []

    for item in matching_items:
        item.status = ListItemStatus.COMPLETED.value
        item.last_completed_at = now
        item.source = ListItemSource.RECEIPT.value

        # Recalculate refresh frequency
        system_days, confidence, next_refresh_at = await calculate_refresh_for_item(
            db, item
        )
        if system_days is not None:
            item.system_refresh_days = system_days
        if confidence is not None:
            item.confidence = confidence
        if next_refresh_at is not None:
            item.next_refresh_at = next_refresh_at

        completed_items.append(item)

    return completed_items


async def match_receipt_purchases(
    db: AsyncSession,
    receipt: Receipt,
    user_id: uuid.UUID,
    purchases: list[Purchase] | None = None,
) -> dict[str, int]:
    """Match all purchases in a receipt to products.

    Updates Purchase records with product_id and matched=True.
    Completes matching list items and recalculates refresh frequencies.

    Args:
        purchases: Pass explicitly to avoid lazy-load in async context.

    Returns summary counts: {'barcode': N, 'exact_name': N, 'fuzzy': N, 'new': N, 'completed_items': N}
    """
    if purchases is None:
        # Fallback: query directly to avoid lazy-load MissingGreenlet error
        result = await db.execute(
            select(Purchase).where(Purchase.receipt_id == receipt.id)
        )
        purchases = list(result.scalars().all())

    counts: dict[str, int] = {
        "barcode": 0,
        "exact_name": 0,
        "fuzzy": 0,
        "new": 0,
        "completed_items": 0,
    }

    for purchase in purchases:
        product, match_type = await match_purchase_to_product(db, purchase)

        # Update purchase record
        purchase.product_id = product.id
        purchase.matched = True
        counts[match_type] += 1

        # Update product barcode if we now have one and the product didn't
        if purchase.barcode and not product.barcode:
            product.barcode = purchase.barcode

        # Complete matching list items (or create new ones)
        completed = await _complete_matching_list_items(
            db, user_id, product, purchase.quantity or 1.0,
        )
        counts["completed_items"] += len(completed)

    await db.flush()

    await logger.ainfo(
        "receipt_matching_complete",
        receipt_id=str(receipt.id),
        counts=counts,
    )

    return counts
