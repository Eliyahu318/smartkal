"""Auto-refresh engine: calculates purchase frequency and confidence for list items.

Uses median of intervals from completion history and receipt purchases to predict
when a user will need an item again. Confidence scoring reflects data quality.
"""

from __future__ import annotations

import statistics
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.list_item import ListItem, ListItemSource, ListItemStatus
from app.models.receipt import Purchase, Receipt

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


def calculate_confidence(num_intervals: int, variance_ratio: float | None) -> float:
    """Calculate confidence score based on number of intervals and variance.

    Confidence tiers:
        1 interval  → 0.2
        2 intervals → 0.3
        3-4         → 0.4
        5-9         → 0.6
        10+         → 0.8
    Low variance bonus: +0.15 (when coefficient of variation < 0.3)
    """
    if num_intervals <= 0:
        return 0.0
    if num_intervals == 1:
        base = 0.2
    elif num_intervals == 2:
        base = 0.3
    elif num_intervals <= 4:
        base = 0.4
    elif num_intervals <= 9:
        base = 0.6
    else:
        base = 0.8

    # Low variance bonus: coefficient of variation < 0.3
    if variance_ratio is not None and variance_ratio < 0.3:
        base += 0.15

    return min(base, 0.95)


def compute_refresh_days(
    intervals_days: list[float],
) -> tuple[int, float]:
    """Compute refresh days from a list of interval lengths (in days).

    Returns (refresh_days, confidence).
    """
    if not intervals_days:
        return 0, 0.0

    median_days = statistics.median(intervals_days)
    num_intervals = len(intervals_days)

    # Calculate coefficient of variation for variance bonus
    variance_ratio: float | None = None
    if num_intervals >= 2:
        mean = statistics.mean(intervals_days)
        if mean > 0:
            stdev = statistics.stdev(intervals_days)
            variance_ratio = stdev / mean

    refresh_days = max(1, round(median_days))
    confidence = calculate_confidence(num_intervals, variance_ratio)

    return refresh_days, confidence


async def gather_completion_timestamps(
    db: AsyncSession,
    item: ListItem,
) -> list[datetime]:
    """Gather timestamps from item's own completion history.

    Currently uses last_completed_at as a single data point.
    In future, a dedicated completion_history table could provide more data.
    """
    timestamps: list[datetime] = []

    if item.last_completed_at is not None:
        timestamps.append(item.last_completed_at)

    return timestamps


async def gather_purchase_timestamps(
    db: AsyncSession,
    user_id: uuid.UUID,
    product_id: uuid.UUID | None,
) -> list[datetime]:
    """Gather purchase timestamps from receipt data for a product."""
    if product_id is None:
        return []

    result = await db.execute(
        select(Receipt.receipt_date)
        .join(Purchase, Purchase.receipt_id == Receipt.id)
        .where(
            Receipt.user_id == user_id,
            Purchase.product_id == product_id,
        )
        .order_by(Receipt.receipt_date)
    )
    dates = result.scalars().all()

    return [
        datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        for d in dates
        if d is not None
    ]


def timestamps_to_intervals(timestamps: list[datetime]) -> list[float]:
    """Convert sorted timestamps to intervals in days."""
    if len(timestamps) < 2:
        return []

    sorted_ts = sorted(timestamps)
    intervals: list[float] = []
    for i in range(1, len(sorted_ts)):
        delta = sorted_ts[i] - sorted_ts[i - 1]
        days = delta.total_seconds() / 86400.0
        if days > 0:
            intervals.append(days)

    return intervals


async def calculate_refresh_for_item(
    db: AsyncSession,
    item: ListItem,
) -> tuple[int | None, float | None, datetime | None]:
    """Calculate refresh parameters for a completed item.

    Returns (system_refresh_days, confidence, next_refresh_at).
    If user has set auto_refresh_days, that takes priority.
    """
    # Gather all timestamps
    completion_ts = await gather_completion_timestamps(db, item)
    purchase_ts = await gather_purchase_timestamps(db, item.user_id, item.product_id)

    # Merge and deduplicate (within same day)
    all_timestamps = completion_ts + purchase_ts
    if not all_timestamps:
        return None, None, None

    # Add the current completion time
    now = datetime.now(timezone.utc)
    all_timestamps.append(now)

    intervals = timestamps_to_intervals(all_timestamps)

    if not intervals:
        return None, None, None

    system_days, confidence = compute_refresh_days(intervals)

    # User override takes priority for scheduling
    effective_days = item.auto_refresh_days if item.auto_refresh_days is not None else system_days
    if item.auto_refresh_days is not None:
        confidence = 0.95

    next_refresh_at = now + timedelta(days=effective_days)

    return system_days, confidence, next_refresh_at


async def activate_overdue_items(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[ListItem]:
    """Find and activate all completed items past their next_refresh_at.

    Returns list of activated items.
    """
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(ListItem).where(
            ListItem.user_id == user_id,
            ListItem.status == ListItemStatus.COMPLETED.value,
            ListItem.next_refresh_at.isnot(None),
            ListItem.next_refresh_at <= now,
        )
    )
    overdue_items = list(result.scalars().all())

    for item in overdue_items:
        item.status = ListItemStatus.ACTIVE.value
        item.last_activated_at = now
        item.source = ListItemSource.AUTO_REFRESH.value
        item.next_refresh_at = None

    if overdue_items:
        await db.flush()
        await logger.ainfo(
            "items_auto_refreshed",
            user_id=str(user_id),
            count=len(overdue_items),
            item_ids=[str(i.id) for i in overdue_items],
        )

    return overdue_items
