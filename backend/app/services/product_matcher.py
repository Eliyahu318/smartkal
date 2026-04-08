"""Product matching service: matches receipt purchases to existing products and list items.

The module is split into two phases:

1. PRODUCT MATCHING (match_purchase_to_product): identifies/creates the global Product
   row that corresponds to a single Purchase. Priority chain:
     a. Barcode exact match
     b. Normalized name exact match
     c. Fuzzy SKU match (rapidfuzz token_set_ratio @ FUZZY_THRESHOLD = 92)
     d. Create new product

2. LIST ITEM RESOLUTION (resolve_list_item_target): given a Product + canonical key,
   decides which of the user's existing ListItems should be completed by this Purchase.
   This is the per-user dedup layer that solves the "עגבניות שרי" / "עגבניות שרי
   פרימיום" / "עגבניות שרי עגול" problem. Priority chain:
     a. Explicit ListItemAlias (user previously merged this product into a list item)
     b. Direct ListItem.product_id link
     c. Same canonical_key on user's list (the new automatic dedup) — also creates a
        new alias row so the next match through the same product is O(1)
     d. Fuzzy fallback against unlinked list items (legacy behavior)

The fuzzy threshold is intentionally HIGH (92, up from 85) because the canonical_key
layer above does the heavy lifting for variant collapsing. Fuzzy is now reserved for
catching genuine typos / word reorderings within true SKU equivalents.
"""

from __future__ import annotations

import re
import unicodedata
import uuid

import structlog
from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.list_item import ListItem, ListItemSource, ListItemStatus
from app.models.list_item_alias import ListItemAlias
from app.models.product import Product
from app.models.receipt import Purchase, Receipt
from app.services.refresh_engine import calculate_refresh_for_item

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

# Raised threshold (was 85) — the canonical_key layer now handles variant collapsing,
# so fuzz is only for catching word reorderings inside the same true SKU.
FUZZY_THRESHOLD = 92.0
# Slightly more lenient threshold for matching against the user's own unlinked list
# items, where typos/abbreviations are common.
LIST_ITEM_FUZZY_THRESHOLD = 88.0


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


# ---------------------------------------------------------------------------
# Phase 1: product matching
# ---------------------------------------------------------------------------


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


async def _match_by_fuzzy_sku(
    db: AsyncSession,
    normalized_name: str,
    threshold: float = FUZZY_THRESHOLD,
) -> Product | None:
    """Find a product by fuzzy SKU match using token_set_ratio.

    Uses token_set_ratio (more discriminating than token_sort_ratio when one name
    has an extra qualifier) at the high FUZZY_THRESHOLD to avoid merging
    distinct SKUs. The canonical_key layer in resolve_list_item_target catches
    the variant collapsing that this fuzzy match deliberately misses.
    """
    result = await db.execute(select(Product))
    products = list(result.scalars().all())

    best_match: Product | None = None
    best_score: float = 0.0

    for product in products:
        score = fuzz.token_set_ratio(normalized_name, product.normalized_name)
        if score >= threshold and score > best_score:
            best_score = score
            best_match = product

    if best_match is not None:
        await logger.ainfo(
            "fuzzy_sku_match_found",
            query=normalized_name,
            matched=best_match.normalized_name,
            score=best_score,
        )

    return best_match


# Backwards-compatible alias used by older test imports.
_match_by_fuzzy = _match_by_fuzzy_sku


def _resolve_canonical_name(
    raw_name: str,
    canonical_hint: str | None,
) -> str:
    """Pick the best canonical key for a purchase.

    Prefers the Claude-extracted canonical_name (richer semantic understanding),
    falls back to the deterministic regex-based canonicalizer if Claude omitted
    the field. Both pass through the same canonical_key normalization so that
    "עגבניות שרי " and "עגבניות שרי" (Claude vs regex) produce the same key.
    """
    # Local import to avoid circular dependency
    from app.services.canonicalizer import canonical_key

    if canonical_hint and canonical_hint.strip():
        return canonical_key(canonical_hint)
    return canonical_key(raw_name)


async def match_purchase_to_product(
    db: AsyncSession,
    purchase: Purchase,
    canonical_hint: str | None = None,
) -> tuple[Product, str]:
    """Match a single purchase to a product using the priority chain.

    Args:
        db: Async session
        purchase: The Purchase to match
        canonical_hint: The canonical_name extracted by Claude (if available).
            Used to populate Product.canonical_name on new products.

    Returns:
        (product, match_type) where match_type is one of:
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

    # 3. Fuzzy SKU match
    product = await _match_by_fuzzy_sku(db, normalized_name)
    if product is not None:
        return product, "fuzzy"

    # 4. Create new product — populate canonical_name from Claude hint or fallback
    canonical_for_product = _resolve_canonical_name(purchase.raw_name, canonical_hint)
    product = Product(
        name=purchase.raw_name,
        normalized_name=normalized_name,
        canonical_name=canonical_for_product or None,
        barcode=purchase.barcode,
    )
    db.add(product)
    await db.flush()

    await logger.ainfo(
        "new_product_created",
        product_id=str(product.id),
        name=purchase.raw_name,
        canonical_name=canonical_for_product,
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


# ---------------------------------------------------------------------------
# Phase 2: per-user list item resolution (the dedup layer)
# ---------------------------------------------------------------------------


async def _alias_target(
    db: AsyncSession,
    user_id: uuid.UUID,
    product_id: uuid.UUID,
) -> ListItem | None:
    """Find a list item the user has explicitly aliased this product to."""
    result = await db.execute(
        select(ListItem)
        .join(ListItemAlias, ListItemAlias.list_item_id == ListItem.id)
        .where(
            ListItemAlias.user_id == user_id,
            ListItemAlias.product_id == product_id,
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _direct_target(
    db: AsyncSession,
    user_id: uuid.UUID,
    product_id: uuid.UUID,
) -> ListItem | None:
    """Find a list item directly linked to this product, preferring active.

    Falls back to a completed item so that re-purchasing an item that was
    completed earlier reuses the existing row instead of creating a duplicate.
    """
    # Active items first (most common case)
    result = await db.execute(
        select(ListItem)
        .where(
            ListItem.user_id == user_id,
            ListItem.product_id == product_id,
            ListItem.status == ListItemStatus.ACTIVE.value,
        )
        .order_by(ListItem.created_at.asc())
        .limit(1)
    )
    item = result.scalar_one_or_none()
    if item is not None:
        return item

    # Then any completed item (so its refresh history continues to grow)
    result = await db.execute(
        select(ListItem)
        .where(
            ListItem.user_id == user_id,
            ListItem.product_id == product_id,
        )
        .order_by(ListItem.created_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _canonical_target(
    db: AsyncSession,
    user_id: uuid.UUID,
    canonical_key_value: str,
) -> ListItem | None:
    """Find a list item with the same canonical_key on this user's list.

    This is the new automatic dedup hook: even if the new purchase produced a
    completely fresh global Product, if the user already has a list item that
    canonicalizes to the same key, the purchase attaches to it.
    """
    if not canonical_key_value:
        return None
    result = await db.execute(
        select(ListItem)
        .where(
            ListItem.user_id == user_id,
            ListItem.canonical_key == canonical_key_value,
        )
        .order_by(
            # Active items beat completed items so the user sees the right thing
            (ListItem.status == ListItemStatus.ACTIVE.value).desc(),
            ListItem.created_at.asc(),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _fuzzy_unlinked_target(
    db: AsyncSession,
    user_id: uuid.UUID,
    product: Product,
) -> ListItem | None:
    """Fuzzy-match the product against the user's unlinked active list items.

    This handles the legacy case where a user manually added an item like
    "חלב" before any receipt was uploaded — when a receipt arrives with the
    same name, we want to link them rather than create a new row.
    """
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
        score = fuzz.token_set_ratio(normalized, item_normalized)
        if score >= LIST_ITEM_FUZZY_THRESHOLD:
            # Backfill the link as a side effect (legacy behavior preserved)
            item.product_id = product.id
            return item
    return None


async def resolve_list_item_target(
    db: AsyncSession,
    user_id: uuid.UUID,
    product: Product,
    canonical_key_value: str,
) -> tuple[ListItem | None, str]:
    """Decide which existing ListItem (if any) should be completed by this purchase.

    Returns (item, source) where source is one of: 'alias', 'direct', 'canonical',
    'fuzzy_unlinked', 'none'. The source value is exposed so callers can update
    counters and so canonical hits can write a new alias row.
    """
    item = await _alias_target(db, user_id, product.id)
    if item is not None:
        return item, "alias"

    item = await _direct_target(db, user_id, product.id)
    if item is not None:
        return item, "direct"

    item = await _canonical_target(db, user_id, canonical_key_value)
    if item is not None:
        return item, "canonical"

    item = await _fuzzy_unlinked_target(db, user_id, product)
    if item is not None:
        return item, "fuzzy_unlinked"

    return None, "none"


async def _ensure_alias(
    db: AsyncSession,
    user_id: uuid.UUID,
    list_item_id: uuid.UUID,
    product_id: uuid.UUID,
) -> None:
    """Insert a ListItemAlias row, idempotently.

    Catches IntegrityError on the (user_id, product_id) unique constraint and
    silently swallows it — the alias already exists, which is the desired state.
    """
    alias = ListItemAlias(
        user_id=user_id,
        list_item_id=list_item_id,
        product_id=product_id,
    )
    db.add(alias)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        # Re-fetch the existing alias to confirm; we don't actually need it.
        await logger.adebug(
            "list_item_alias_already_exists",
            user_id=str(user_id),
            product_id=str(product_id),
            list_item_id=str(list_item_id),
        )


async def _complete_matching_list_items(
    db: AsyncSession,
    user_id: uuid.UUID,
    product: Product,
    canonical_key_value: str,
    purchase_quantity: float = 1.0,
) -> tuple[list[ListItem], str]:
    """Find or create a list item for this purchase and mark it completed.

    Returns:
        (completed_items, resolution_source) where resolution_source identifies
        how the list item was located: 'alias', 'direct', 'canonical',
        'fuzzy_unlinked', or 'created' (for a brand-new list item).
    """
    from datetime import datetime, timezone

    target, source = await resolve_list_item_target(
        db, user_id, product, canonical_key_value
    )

    now = datetime.now(timezone.utc)

    if target is None:
        # No existing list item — create a new one as completed so we still
        # learn the purchase pattern.
        from app.services.categorizer import auto_categorize

        category_id = product.category_id
        if category_id is None:
            category_id = await auto_categorize(db, user_id, product.name)
            if category_id is not None:
                product.category_id = category_id
        if category_id is None:
            category_id = await _get_default_category_id(db, user_id)

        target = ListItem(
            user_id=user_id,
            product_id=product.id,
            category_id=category_id,
            name=product.name,
            canonical_key=canonical_key_value or None,
            quantity=str(purchase_quantity) if purchase_quantity != 1.0 else None,
            status=ListItemStatus.COMPLETED.value,
            source=ListItemSource.RECEIPT.value,
            last_completed_at=now,
        )
        db.add(target)
        try:
            await db.flush()
        except IntegrityError:
            # Race: another concurrent upload just created a list item with the
            # same canonical_key. Roll back the optimistic insert and re-resolve.
            await db.rollback()
            target, source = await resolve_list_item_target(
                db, user_id, product, canonical_key_value
            )
            if target is None:
                # Genuine surprise — bail out and let the upper layer handle it.
                raise
            source = source if source != "none" else "canonical"
        else:
            source = "created"

    # If we found a list item via canonical_key (or fuzzy_unlinked), persist
    # the alias so the next purchase of the same product is O(1).
    if source in {"canonical", "fuzzy_unlinked"}:
        await _ensure_alias(db, user_id, target.id, product.id)
        # If the existing item had no canonical_key yet, backfill it now.
        if not target.canonical_key and canonical_key_value:
            target.canonical_key = canonical_key_value

    # Newly created items already have canonical_key set; backfill if missing
    # (e.g. for items found via direct product_id link from before this feature).
    if not target.canonical_key and canonical_key_value:
        target.canonical_key = canonical_key_value

    # Mark completed and recalculate refresh
    target.status = ListItemStatus.COMPLETED.value
    target.last_completed_at = now
    target.source = ListItemSource.RECEIPT.value

    system_days, confidence, next_refresh_at = await calculate_refresh_for_item(
        db, target
    )
    if system_days is not None:
        target.system_refresh_days = system_days
    if confidence is not None:
        target.confidence = confidence
    if next_refresh_at is not None:
        target.next_refresh_at = next_refresh_at

    return [target], source


async def match_receipt_purchases(
    db: AsyncSession,
    receipt: Receipt,
    user_id: uuid.UUID,
    purchases: list[Purchase] | None = None,
    canonicals: list[str | None] | None = None,
) -> dict[str, int]:
    """Match all purchases in a receipt to products and complete list items.

    Args:
        purchases: Pass explicitly to avoid lazy-load in async context.
        canonicals: Parallel list of canonical_name hints from the parser. Same
            length as `purchases` if provided. If None or shorter, missing entries
            fall back to the deterministic canonicalizer.

    Returns:
        Summary counters: {
            'barcode', 'exact_name', 'fuzzy', 'new',
            'completed_items', 'auto_merged_to_existing', 'completed_via_alias'
        }
    """
    if purchases is None:
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
        "auto_merged_to_existing": 0,
        "completed_via_alias": 0,
    }

    for idx, purchase in enumerate(purchases):
        canonical_hint: str | None = None
        if canonicals is not None and idx < len(canonicals):
            canonical_hint = canonicals[idx]

        product, match_type = await match_purchase_to_product(
            db, purchase, canonical_hint=canonical_hint
        )

        purchase.product_id = product.id
        purchase.matched = True
        counts[match_type] += 1

        # Update product barcode if we now have one and the product didn't
        if purchase.barcode and not product.barcode:
            product.barcode = purchase.barcode

        # Backfill product canonical_name if missing (rare: when an old product
        # is matched by an exact name and Claude has now extracted a canonical).
        if product.canonical_name is None:
            inferred = _resolve_canonical_name(purchase.raw_name, canonical_hint)
            if inferred:
                product.canonical_name = inferred

        # Resolve / create list item and complete it
        canonical_key_value = _resolve_canonical_name(
            purchase.raw_name, canonical_hint
        )
        completed, source = await _complete_matching_list_items(
            db,
            user_id,
            product,
            canonical_key_value=canonical_key_value,
            purchase_quantity=purchase.quantity or 1.0,
        )
        counts["completed_items"] += len(completed)

        if source == "canonical":
            counts["auto_merged_to_existing"] += 1
        elif source == "alias":
            counts["completed_via_alias"] += 1

    await db.flush()

    await logger.ainfo(
        "receipt_matching_complete",
        receipt_id=str(receipt.id),
        counts=counts,
    )

    return counts
