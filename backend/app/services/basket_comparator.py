"""Basket price comparison across Israeli supermarket chains.

Given a list of product IDs, calculates the total basket cost at each chain
using the most recent PriceHistory records. Returns a ranked comparison
with coverage indicators for partial matches.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price_history import PriceHistory

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


@dataclass
class StoreBasket:
    """Aggregated basket total for a single store chain."""

    store_name: str
    total: Decimal = Decimal("0")
    matched_count: int = 0


@dataclass
class BasketComparison:
    """Full basket comparison result across all chains."""

    comparisons: list[StoreBasket] = field(default_factory=list)
    total_items: int = 0
    matched_items: int = 0
    cheapest_store: str = ""
    cheapest_total: Decimal = Decimal("0")
    current_total: Decimal = Decimal("0")
    savings: Decimal = Decimal("0")


async def _get_latest_prices_by_product(
    db: AsyncSession,
    product_ids: list[uuid.UUID],
) -> dict[uuid.UUID, dict[str, Decimal]]:
    """Get the latest price per store for each product.

    Returns: {product_id: {store_name: price}}
    """
    if not product_ids:
        return {}

    # Subquery: latest observed_at per (product_id, store_name)
    latest_subq = (
        select(
            PriceHistory.product_id,
            PriceHistory.store_name,
            func.max(PriceHistory.observed_at).label("max_observed"),
        )
        .where(PriceHistory.product_id.in_(product_ids))
        .group_by(PriceHistory.product_id, PriceHistory.store_name)
        .subquery()
    )

    # Join back to get the actual price at that timestamp
    stmt = (
        select(
            PriceHistory.product_id,
            PriceHistory.store_name,
            PriceHistory.price,
        )
        .join(
            latest_subq,
            (PriceHistory.product_id == latest_subq.c.product_id)
            & (PriceHistory.store_name == latest_subq.c.store_name)
            & (PriceHistory.observed_at == latest_subq.c.max_observed),
        )
    )

    result = await db.execute(stmt)
    rows = result.all()

    prices: dict[uuid.UUID, dict[str, Decimal]] = {}
    for row in rows:
        pid: uuid.UUID = row[0]
        store: str = row[1]
        price: Decimal = row[2]
        if pid not in prices:
            prices[pid] = {}
        prices[pid][store] = price

    return prices


async def compare_basket(
    db: AsyncSession,
    product_ids: list[uuid.UUID],
    current_store: str | None = None,
    price_map: dict[uuid.UUID, dict[str, Decimal]] | None = None,
) -> BasketComparison:
    """Compare a basket of products across supermarket chains.

    Args:
        db: Database session.
        product_ids: List of product UUIDs to compare.
        current_store: The store where the user shopped (for savings calc).
        price_map: Pre-fetched price data. If None, fetched from DB.

    Returns:
        BasketComparison with per-store totals, coverage, and savings info.
    """
    total_items = len(product_ids)
    if total_items == 0:
        return BasketComparison(total_items=0)

    # Get latest prices per product per store
    if price_map is None:
        price_map = await _get_latest_prices_by_product(db, product_ids)
    matched_items = len(price_map)

    if matched_items == 0:
        return BasketComparison(total_items=total_items, matched_items=0)

    # Aggregate totals per store (only count products that have a price at that store)
    store_totals: dict[str, StoreBasket] = {}

    for _pid, store_prices in price_map.items():
        for store_name, price in store_prices.items():
            if store_name not in store_totals:
                store_totals[store_name] = StoreBasket(store_name=store_name)
            store_totals[store_name].total += price
            store_totals[store_name].matched_count += 1

    # Sort by total ascending (cheapest first)
    comparisons = sorted(store_totals.values(), key=lambda s: s.total)

    if not comparisons:
        return BasketComparison(
            total_items=total_items,
            matched_items=matched_items,
        )

    cheapest = comparisons[0]

    # Determine current_total: use the specified store if available, else most expensive
    current_total = Decimal("0")
    if current_store and current_store in store_totals:
        current_total = store_totals[current_store].total
    elif len(comparisons) > 1:
        # Use the most expensive store as baseline for savings
        current_total = comparisons[-1].total
    else:
        current_total = cheapest.total

    savings = current_total - cheapest.total

    await logger.ainfo(
        "basket_comparison_complete",
        total_items=total_items,
        matched_items=matched_items,
        store_count=len(comparisons),
        cheapest_store=cheapest.store_name,
        cheapest_total=str(cheapest.total),
        savings=str(savings),
    )

    return BasketComparison(
        comparisons=comparisons,
        total_items=total_items,
        matched_items=matched_items,
        cheapest_store=cheapest.store_name,
        cheapest_total=cheapest.total,
        current_total=current_total,
        savings=savings,
    )


@dataclass
class CategoryRecommendation:
    """Cheapest store recommendation for a single product category."""

    category_name: str
    cheapest_store: str
    cheapest_total: Decimal = Decimal("0")
    savings: Decimal = Decimal("0")


async def compare_basket_by_category(
    db: AsyncSession,
    product_category_map: dict[uuid.UUID, str],
    price_map: dict[uuid.UUID, dict[str, Decimal]] | None = None,
) -> list[CategoryRecommendation]:
    """Compare basket prices grouped by category, returning cheapest store per category.

    Args:
        db: Database session.
        product_category_map: Mapping of product_id → category_name.
        price_map: Pre-fetched price data. If None, fetched from DB.

    Returns:
        List of CategoryRecommendation sorted by savings descending.
    """
    if not product_category_map:
        return []

    all_product_ids = list(product_category_map.keys())
    if price_map is None:
        price_map = await _get_latest_prices_by_product(db, all_product_ids)

    # Group products by category
    category_products: dict[str, list[uuid.UUID]] = {}
    for pid, cat_name in product_category_map.items():
        category_products.setdefault(cat_name, []).append(pid)

    recommendations: list[CategoryRecommendation] = []

    for cat_name, pids in category_products.items():
        # Aggregate per-store totals for this category
        store_totals: dict[str, Decimal] = {}
        for pid in pids:
            if pid not in price_map:
                continue
            for store, price in price_map[pid].items():
                store_totals[store] = store_totals.get(store, Decimal("0")) + price

        # Need at least 2 stores for a meaningful comparison
        if len(store_totals) < 2:
            continue

        cheapest_store = min(store_totals, key=lambda s: store_totals[s])
        most_expensive_total = max(store_totals.values())
        cheapest_total = store_totals[cheapest_store]

        recommendations.append(
            CategoryRecommendation(
                category_name=cat_name,
                cheapest_store=cheapest_store,
                cheapest_total=cheapest_total,
                savings=most_expensive_total - cheapest_total,
            )
        )

    # Sort by savings descending (most impactful categories first)
    recommendations.sort(key=lambda r: r.savings, reverse=True)
    return recommendations
