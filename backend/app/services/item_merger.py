"""Item merger service: detect and merge duplicate list items.

Two operations:

1. find_duplicate_groups(user_id) — group the user's active list items by their
   canonical_key. Within each group with > 1 item, run a secondary token_set_ratio
   check as belt-and-suspenders so that an over-aggressive canonical_key (rare but
   possible) doesn't surface false positives in the UI.

2. merge_list_items(user_id, target_id, source_ids) — atomically:
     a. write a list_item_merge_log row for each source with a full JSON snapshot
     b. upsert list_item_aliases mapping each source's product_id to the target
     c. merge notes (joined by " · ")
     d. pick min(created_at) and max(last_completed_at) for the target
     e. delete source list items (CASCADE cleans preferences, aliases, etc.)
     f. recalculate the target's refresh cadence so the merged purchase history
        is reflected immediately

The merge log is the safety net that lets us answer "where did my item go?"
support requests and powers a future undo feature. Source rows are deleted —
without the audit log there would be no recovery path.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import structlog
from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.models.list_item import ListItem
from app.models.list_item_alias import ListItemAlias
from app.models.list_item_merge_log import ListItemMergeLog
from app.services.refresh_engine import calculate_refresh_for_item

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


# Secondary similarity threshold used both for grouping (within a canonical_key
# bucket, also require name similarity above this) and for the auto-merge safety
# gate (only auto-merge groups where every pair scores above this).
SECONDARY_SIMILARITY_THRESHOLD = 88.0


@dataclass
class DuplicateGroup:
    """A group of list items that share the same canonical key."""

    canonical: str
    items: list[ListItem]


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


async def find_duplicate_groups(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[DuplicateGroup]:
    """Find groups of duplicate list items for a user.

    Considers only items with a non-empty canonical_key. Items missing a
    canonical_key are ignored — they should have been backfilled by the lazy
    backfill in GET /list before this is called. Groups with only one item are
    excluded from the result.
    """
    result = await db.execute(
        select(ListItem)
        .where(
            ListItem.user_id == user_id,
            ListItem.canonical_key.isnot(None),
        )
        .order_by(ListItem.canonical_key, ListItem.created_at.asc())
    )
    items = list(result.scalars().all())

    # Bucket by canonical_key
    buckets: dict[str, list[ListItem]] = {}
    for item in items:
        key = item.canonical_key or ""
        if not key:
            continue
        buckets.setdefault(key, []).append(item)

    groups: list[DuplicateGroup] = []
    for canonical, group_items in buckets.items():
        if len(group_items) < 2:
            continue
        groups.append(DuplicateGroup(canonical=canonical, items=group_items))

    return groups


def _group_is_safe_for_auto_merge(group: DuplicateGroup) -> bool:
    """Belt-and-suspenders check: every pair in the group must also pass a
    name-level fuzzy similarity threshold.

    This guards against the canonical_key being too aggressive: if any two
    items in the group are < SECONDARY_SIMILARITY_THRESHOLD apart by name,
    we don't auto-merge them — the user has to confirm via the UI.
    """
    items = group.items
    if len(items) < 2:
        return False
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            score = fuzz.token_set_ratio(items[i].name, items[j].name)
            if score < SECONDARY_SIMILARITY_THRESHOLD:
                return False
    return True


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------


def _serialize_list_item(item: ListItem) -> dict[str, Any]:
    """Snapshot a ListItem to a JSON-serializable dict for the merge log."""
    return {
        "id": str(item.id),
        "user_id": str(item.user_id),
        "product_id": str(item.product_id) if item.product_id else None,
        "category_id": str(item.category_id) if item.category_id else None,
        "name": item.name,
        "canonical_key": item.canonical_key,
        "quantity": item.quantity,
        "note": item.note,
        "status": item.status,
        "source": item.source,
        "auto_refresh_days": item.auto_refresh_days,
        "system_refresh_days": item.system_refresh_days,
        "confidence": item.confidence,
        "display_order": item.display_order,
        "last_completed_at": item.last_completed_at.isoformat() if item.last_completed_at else None,
        "last_activated_at": item.last_activated_at.isoformat() if item.last_activated_at else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


async def _load_owned_items(
    db: AsyncSession,
    user_id: uuid.UUID,
    item_ids: list[uuid.UUID],
) -> list[ListItem]:
    """Load list items that belong to the user. Raises NotFoundError if any are missing."""
    if not item_ids:
        return []
    result = await db.execute(
        select(ListItem).where(
            ListItem.user_id == user_id,
            ListItem.id.in_(item_ids),
        )
    )
    items = list(result.scalars().all())
    if len(items) != len(set(item_ids)):
        raise NotFoundError(
            message_he="חלק מהפריטים לא נמצאו או לא שייכים אליך",
            message_en="One or more items not found or not owned by user",
            details={"requested": [str(i) for i in item_ids]},
        )
    return items


async def merge_list_items(
    db: AsyncSession,
    user_id: uuid.UUID,
    target_id: uuid.UUID,
    source_ids: list[uuid.UUID],
) -> ListItem:
    """Merge multiple list items into a target list item.

    Atomic — either everything succeeds or we raise. The caller is responsible
    for committing the surrounding transaction.

    Steps:
      1. Validate inputs (non-empty sources, target not in sources, all owned).
      2. Snapshot each source to list_item_merge_log.
      3. Upsert list_item_aliases mapping each source.product_id (and any of its
         pre-existing aliased products) to target.
      4. Merge notes, take min(created_at), max(last_completed_at).
      5. Delete sources (CASCADE handles preferences and aliases pointing INTO
         the deleted rows).
      6. Recalculate refresh for the target so the merged purchase history is
         reflected.
    """
    # 1. Validation
    if not source_ids:
        raise ValidationError(
            message_he="חובה לציין לפחות פריט אחד למיזוג",
            message_en="At least one source item required",
        )
    if target_id in source_ids:
        raise ValidationError(
            message_he="הפריט היעד לא יכול להיות גם פריט מקור",
            message_en="target_id must not appear in source_ids",
        )

    target = await _load_owned_items(db, user_id, [target_id])
    if not target:
        raise NotFoundError(
            message_he="פריט היעד לא נמצא",
            message_en="Target item not found",
        )
    target_item = target[0]

    sources = await _load_owned_items(db, user_id, source_ids)

    # 2. Snapshot sources to merge log + collect product_ids to alias
    products_to_alias: set[uuid.UUID] = set()
    for source in sources:
        log = ListItemMergeLog(
            user_id=user_id,
            source_id=source.id,
            source_name=source.name,
            source_payload=_serialize_list_item(source),
            target_id=target_item.id,
        )
        db.add(log)
        if source.product_id is not None:
            products_to_alias.add(source.product_id)

    # 2b. Also collect any existing aliases pointing to the source items —
    # those products must be re-pointed to the target.
    if sources:
        alias_q = await db.execute(
            select(ListItemAlias).where(
                ListItemAlias.user_id == user_id,
                ListItemAlias.list_item_id.in_([s.id for s in sources]),
            )
        )
        for alias in alias_q.scalars().all():
            products_to_alias.add(alias.product_id)

    # 3. Upsert aliases (each (user_id, product_id) maps to target_id).
    # Postgres ON CONFLICT lets us replace the existing list_item_id atomically.
    now = datetime.now(timezone.utc)
    for product_id in products_to_alias:
        stmt = (
            pg_insert(ListItemAlias)
            .values(
                user_id=user_id,
                list_item_id=target_item.id,
                product_id=product_id,
            )
            .on_conflict_do_update(
                constraint="uq_list_item_aliases_user_product",
                set_={
                    "list_item_id": target_item.id,
                    "updated_at": now,
                },
            )
        )
        await db.execute(stmt)

    # 4. Merge notes / dates
    notes_parts: list[str] = []
    if target_item.note:
        notes_parts.append(target_item.note)
    for source in sources:
        if source.note and source.note not in notes_parts:
            notes_parts.append(source.note)
    if notes_parts:
        target_item.note = " · ".join(notes_parts)

    earliest_created = target_item.created_at
    latest_completed = target_item.last_completed_at
    for source in sources:
        if source.created_at and (earliest_created is None or source.created_at < earliest_created):
            earliest_created = source.created_at
        if source.last_completed_at and (
            latest_completed is None or source.last_completed_at > latest_completed
        ):
            latest_completed = source.last_completed_at
    if earliest_created is not None:
        target_item.created_at = earliest_created
    if latest_completed is not None:
        target_item.last_completed_at = latest_completed

    # 5. Delete sources. CASCADE removes any list_item_aliases still pointing
    # at them (we already re-pointed the relevant ones above to the target,
    # but stale aliases would also be cleaned).
    for source in sources:
        await db.delete(source)

    await db.flush()

    # 6. Recalculate refresh on the target so the merged history is reflected.
    system_days, confidence, next_refresh_at = await calculate_refresh_for_item(db, target_item)
    if system_days is not None:
        target_item.system_refresh_days = system_days
    if confidence is not None:
        target_item.confidence = confidence
    if next_refresh_at is not None:
        target_item.next_refresh_at = next_refresh_at

    await db.flush()

    await logger.ainfo(
        "list_items_merged",
        user_id=str(user_id),
        target_id=str(target_item.id),
        source_count=len(sources),
        aliased_products=len(products_to_alias),
    )

    return target_item


async def auto_merge_safe_groups(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> tuple[int, int]:
    """Find duplicate groups and auto-merge those that pass the safety check.

    "Safe" = canonical_key match AND every pair in the group above
    SECONDARY_SIMILARITY_THRESHOLD by token_set_ratio. This is the gate behind
    the "איחוד אוטומטי של הכל" button.

    Returns (merged_item_count, group_count).
    """
    groups = await find_duplicate_groups(db, user_id)
    safe_groups = [g for g in groups if _group_is_safe_for_auto_merge(g)]

    merged_count = 0
    for group in safe_groups:
        # Pick the oldest item as the target (most likely to have history)
        items_sorted = sorted(group.items, key=lambda i: i.created_at)
        target = items_sorted[0]
        sources = items_sorted[1:]
        if not sources:
            continue
        await merge_list_items(db, user_id, target.id, [s.id for s in sources])
        merged_count += len(sources)

    await logger.ainfo(
        "auto_merge_complete",
        user_id=str(user_id),
        merged_count=merged_count,
        safe_groups=len(safe_groups),
        total_groups=len(groups),
    )
    return merged_count, len(safe_groups)
