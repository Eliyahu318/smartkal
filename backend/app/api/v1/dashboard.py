"""US-024: Dashboard backend API.

Spending analytics endpoints for category breakdown, store spending,
and monthly trend data — all scoped to the authenticated user.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.category import Category
from app.models.list_item import ListItem
from app.models.list_item_alias import ListItemAlias
from app.models.receipt import Purchase, Receipt
from app.models.user import User
from app.services.basket_comparator import (
    _get_latest_prices_by_product,
    compare_basket,
    compare_basket_by_category,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class CategorySpending(BaseModel):
    category_name: str
    total: float
    percentage: float


class SpendingResponse(BaseModel):
    period: str
    total_spending: float
    categories: list[CategorySpending]


class StoreSpending(BaseModel):
    store_name: str
    total: float
    receipt_count: int
    percentage: float


class StoresResponse(BaseModel):
    stores: list[StoreSpending]
    total_spending: float


class MonthTrend(BaseModel):
    month: str
    total: float


class TrendsResponse(BaseModel):
    months: list[MonthTrend]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _period_date_range(period: str) -> tuple[date, date]:
    """Return (start_date, end_date) for the given period string."""
    today = date.today()
    if period == "week":
        start = today - timedelta(days=today.weekday())
        return start, today
    if period == "year":
        return date(today.year, 1, 1), today
    # Default: month
    return date(today.year, today.month, 1), today


# ---------------------------------------------------------------------------
# GET /api/v1/dashboard/spending?period=month
# ---------------------------------------------------------------------------


@router.get("/spending", response_model=SpendingResponse)
async def get_spending_by_category(
    period: str = Query("month", pattern="^(week|month|year)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SpendingResponse:
    """Spending breakdown by category for the given period."""
    start_date, end_date = _period_date_range(period)

    # The category for a purchase is determined by the user's OWN list_items —
    # not by any field on the global Product table (which has no category_id
    # since migration 0003). Two paths can link a purchase's product_id to
    # a list_item:
    #   (a) direct: list_items.product_id == purchases.product_id (the
    #       "first time the product was bought" path)
    #   (b) via alias: list_item_aliases.product_id == purchases.product_id
    #       (when canonical-key dedup merged this product into an existing
    #       list item with a different product_id)
    # We UNION both into a single (product_id → category_id) lookup.
    direct_link = (
        select(
            ListItem.product_id.label("pid"),
            ListItem.category_id.label("cid"),
        )
        .where(
            ListItem.user_id == current_user.id,
            ListItem.product_id.is_not(None),
        )
    )
    alias_link = (
        select(
            ListItemAlias.product_id.label("pid"),
            ListItem.category_id.label("cid"),
        )
        .join(ListItem, ListItem.id == ListItemAlias.list_item_id)
        .where(ListItemAlias.user_id == current_user.id)
    )
    user_product_categories = direct_link.union(alias_link).subquery("upc")

    cat_name_expr = func.coalesce(Category.name, "אחר")
    stmt = (
        select(
            cat_name_expr.label("cat_name"),
            func.coalesce(func.sum(Purchase.total_price), Decimal(0)).label("cat_total"),
        )
        .select_from(Purchase)
        .join(Receipt, Purchase.receipt_id == Receipt.id)
        .outerjoin(
            user_product_categories,
            user_product_categories.c.pid == Purchase.product_id,
        )
        .outerjoin(Category, Category.id == user_product_categories.c.cid)
        .where(
            Receipt.user_id == current_user.id,
            Receipt.receipt_date >= start_date,
            Receipt.receipt_date <= end_date,
        )
        .group_by(cat_name_expr)
        .order_by(func.sum(Purchase.total_price).desc())
    )

    result = await db.execute(stmt)
    rows = result.all()

    grand_total = float(sum(Decimal(str(row[1])) for row in rows))

    categories = [
        CategorySpending(
            category_name=str(row[0]),
            total=float(row[1]),
            percentage=round(float(row[1]) / grand_total * 100, 1) if grand_total > 0 else 0,
        )
        for row in rows
    ]

    await logger.ainfo(
        "dashboard_spending",
        user_id=str(current_user.id),
        period=period,
        total=grand_total,
        category_count=len(categories),
    )

    return SpendingResponse(
        period=period,
        total_spending=grand_total,
        categories=categories,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/dashboard/stores
# ---------------------------------------------------------------------------


@router.get("/stores", response_model=StoresResponse)
async def get_spending_by_store(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StoresResponse:
    """Spending breakdown by store chain."""
    store_expr = func.coalesce(Receipt.store_name, "לא ידוע")
    stmt = (
        select(
            store_expr.label("store"),
            func.coalesce(func.sum(Receipt.total_amount), Decimal(0)).label("store_total"),
            func.count(Receipt.id).label("receipt_count"),
        )
        .where(Receipt.user_id == current_user.id)
        .group_by(store_expr)
        .order_by(func.sum(Receipt.total_amount).desc())
    )

    result = await db.execute(stmt)
    rows = result.all()

    grand_total = float(sum(Decimal(str(row[1])) for row in rows))

    stores = [
        StoreSpending(
            store_name=str(row[0]),
            total=float(row[1]),
            receipt_count=int(row[2]),
            percentage=round(float(row[1]) / grand_total * 100, 1) if grand_total > 0 else 0,
        )
        for row in rows
    ]

    await logger.ainfo(
        "dashboard_stores",
        user_id=str(current_user.id),
        total=grand_total,
        store_count=len(stores),
    )

    return StoresResponse(stores=stores, total_spending=grand_total)


# ---------------------------------------------------------------------------
# GET /api/v1/dashboard/trends
# ---------------------------------------------------------------------------


@router.get("/trends", response_model=TrendsResponse)
async def get_spending_trends(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TrendsResponse:
    """Monthly spending trend over the last 12 months."""
    today = date.today()
    twelve_months_ago = date(today.year - 1, today.month, 1)

    # Extract year-month from receipt_date for grouping
    month_expr = func.to_char(Receipt.receipt_date, "YYYY-MM")
    stmt = (
        select(
            month_expr.label("month"),
            func.coalesce(func.sum(Receipt.total_amount), Decimal(0)).label("month_total"),
        )
        .where(
            Receipt.user_id == current_user.id,
            Receipt.receipt_date >= twelve_months_ago,
        )
        .group_by(month_expr)
        .order_by(month_expr)
    )

    result = await db.execute(stmt)
    rows = result.all()

    months = [
        MonthTrend(
            month=str(row[0]),
            total=float(row[1]),
        )
        for row in rows
    ]

    await logger.ainfo(
        "dashboard_trends",
        user_id=str(current_user.id),
        month_count=len(months),
    )

    return TrendsResponse(months=months)


# ---------------------------------------------------------------------------
# GET /api/v1/dashboard/smart-basket
# ---------------------------------------------------------------------------


class StoreComparisonItem(BaseModel):
    store_name: str
    total: float
    matched_count: int


class CategoryRecommendationItem(BaseModel):
    category_name: str
    cheapest_store: str
    cheapest_total: float
    savings: float


class SmartBasketResponse(BaseModel):
    comparisons: list[StoreComparisonItem]
    total_items: int
    matched_items: int
    cheapest_store: str
    cheapest_total: float
    savings: float
    coverage_text: str
    category_recommendations: list[CategoryRecommendationItem]


@router.get("/smart-basket", response_model=SmartBasketResponse)
async def get_smart_basket(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SmartBasketResponse:
    """Compare active shopping list across stores with per-category breakdown.

    Uses receipt-based price history to recommend the cheapest store overall
    and per product category.
    """
    # Fetch active list items with their categories
    result = await db.execute(
        select(ListItem)
        .options(selectinload(ListItem.category))
        .where(
            ListItem.user_id == current_user.id,
            ListItem.status == "active",
        )
    )
    items = list(result.scalars().all())

    total_items = len(items)

    # Build product_ids and product → category mapping
    product_ids: list[uuid.UUID] = []
    product_category_map: dict[uuid.UUID, str] = {}
    for item in items:
        if item.product_id is not None:
            product_ids.append(item.product_id)
            cat_name = item.category.name if item.category else "אחר"
            product_category_map[item.product_id] = cat_name

    # Empty response when no products to compare
    if not product_ids:
        return SmartBasketResponse(
            comparisons=[],
            total_items=total_items,
            matched_items=0,
            cheapest_store="",
            cheapest_total=0,
            savings=0,
            coverage_text="",
            category_recommendations=[],
        )

    # Fetch price map once and share across both comparisons
    price_map = await _get_latest_prices_by_product(db, product_ids)

    # Overall store comparison
    comparison = await compare_basket(db, product_ids, price_map=price_map)

    # Per-category recommendations
    cat_recs = await compare_basket_by_category(
        db, product_category_map, price_map=price_map
    )

    # Build coverage text
    matched = comparison.matched_items
    if total_items > 0 and matched < total_items:
        pct = int(matched / total_items * 100)
        coverage_text = f"השוואה על {matched} מתוך {total_items} מוצרים ({pct}%)"
    elif total_items > 0:
        coverage_text = f"השוואה על כל {total_items} המוצרים"
    else:
        coverage_text = ""

    await logger.ainfo(
        "dashboard_smart_basket",
        user_id=str(current_user.id),
        total_items=total_items,
        matched_items=matched,
        cheapest_store=comparison.cheapest_store,
        category_recs=len(cat_recs),
    )

    return SmartBasketResponse(
        comparisons=[
            StoreComparisonItem(
                store_name=s.store_name,
                total=float(s.total),
                matched_count=s.matched_count,
            )
            for s in comparison.comparisons
        ],
        total_items=total_items,
        matched_items=matched,
        cheapest_store=comparison.cheapest_store,
        cheapest_total=float(comparison.cheapest_total),
        savings=float(comparison.savings),
        coverage_text=coverage_text,
        category_recommendations=[
            CategoryRecommendationItem(
                category_name=r.category_name,
                cheapest_store=r.cheapest_store,
                cheapest_total=float(r.cheapest_total),
                savings=float(r.savings),
            )
            for r in cat_recs
        ],
    )
