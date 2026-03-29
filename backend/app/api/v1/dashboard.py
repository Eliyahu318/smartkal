"""US-024: Dashboard backend API.

Spending analytics endpoints for category breakdown, store spending,
and monthly trend data — all scoped to the authenticated user.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.category import Category
from app.models.product import Product
from app.models.receipt import Purchase, Receipt
from app.models.user import User

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

    # Sum purchase totals grouped by category name.
    # Purchase → Product → Category gives us the category name.
    # Purchases without a matched product are grouped under "אחר".
    stmt = (
        select(
            func.coalesce(Category.name, "אחר").label("cat_name"),
            func.coalesce(func.sum(Purchase.total_price), Decimal(0)).label("cat_total"),
        )
        .select_from(Purchase)
        .join(Receipt, Purchase.receipt_id == Receipt.id)
        .outerjoin(Product, Purchase.product_id == Product.id)
        .outerjoin(Category, Product.category_id == Category.id)
        .where(
            Receipt.user_id == current_user.id,
            Receipt.receipt_date >= start_date,
            Receipt.receipt_date <= end_date,
        )
        .group_by(func.coalesce(Category.name, "אחר"))
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
    stmt = (
        select(
            func.coalesce(Receipt.store_name, "לא ידוע").label("store"),
            func.coalesce(func.sum(Receipt.total_amount), Decimal(0)).label("store_total"),
            func.count(Receipt.id).label("receipt_count"),
        )
        .where(Receipt.user_id == current_user.id)
        .group_by(func.coalesce(Receipt.store_name, "לא ידוע"))
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
    twelve_months_ago = date(today.year - 1, today.month, 1) if today.month <= 12 else date(today.year, 1, 1)

    # Extract year-month from receipt_date for grouping
    stmt = (
        select(
            func.to_char(Receipt.receipt_date, "YYYY-MM").label("month"),
            func.coalesce(func.sum(Receipt.total_amount), Decimal(0)).label("month_total"),
        )
        .where(
            Receipt.user_id == current_user.id,
            Receipt.receipt_date >= twelve_months_ago,
        )
        .group_by(func.to_char(Receipt.receipt_date, "YYYY-MM"))
        .order_by(func.to_char(Receipt.receipt_date, "YYYY-MM"))
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
