"""US-023: Price comparison endpoints.

Compare shopping list or receipt basket across Israeli supermarket chains.
Returns ranked store comparisons with coverage indicators.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import structlog

from app.config import get_settings
from app.core.errors import NotFoundError
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.list_item import ListItem
from app.models.receipt import Receipt
from app.models.user import User
from app.services.basket_comparator import StoreBasket, compare_basket
from app.services.price_comparator import fetch_prices_for_products

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

router = APIRouter(prefix="/prices", tags=["prices"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class StoreComparisonResponse(BaseModel):
    store_name: str
    total: float
    matched_count: int


class BasketComparisonResponse(BaseModel):
    comparisons: list[StoreComparisonResponse]
    total_items: int
    matched_items: int
    cheapest_store: str
    cheapest_total: float
    current_total: float
    savings: float
    coverage_text: str


def _build_response(
    comparisons: list[StoreBasket],
    total_items: int,
    matched_items: int,
    cheapest_store: str,
    cheapest_total: Decimal,
    current_total: Decimal,
    savings: Decimal,
) -> BasketComparisonResponse:
    """Build the API response with coverage text."""
    if total_items > 0 and matched_items < total_items:
        pct = int(matched_items / total_items * 100)
        coverage_text = f"השוואה על {matched_items} מתוך {total_items} מוצרים ({pct}%)"
    elif total_items > 0:
        coverage_text = f"השוואה על כל {total_items} המוצרים"
    else:
        coverage_text = ""

    store_responses = [
        StoreComparisonResponse(
            store_name=s.store_name,
            total=float(s.total),
            matched_count=s.matched_count,
        )
        for s in comparisons
    ]

    return BasketComparisonResponse(
        comparisons=store_responses,
        total_items=total_items,
        matched_items=matched_items,
        cheapest_store=cheapest_store,
        cheapest_total=float(cheapest_total),
        current_total=float(current_total),
        savings=float(savings),
        coverage_text=coverage_text,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/prices/compare-receipt/{receipt_id}
# ---------------------------------------------------------------------------


@router.get("/compare-receipt/{receipt_id}", response_model=BasketComparisonResponse)
async def compare_receipt_prices(
    receipt_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BasketComparisonResponse:
    """Compare a receipt's basket across supermarket chains."""
    result = await db.execute(
        select(Receipt)
        .options(selectinload(Receipt.purchases))
        .where(Receipt.id == receipt_id, Receipt.user_id == current_user.id)
    )
    receipt = result.scalar_one_or_none()

    if receipt is None:
        raise NotFoundError(
            message_he="הקבלה לא נמצאה",
            message_en="Receipt not found",
        )

    # Collect product IDs from matched purchases
    product_ids = [
        p.product_id
        for p in receipt.purchases
        if p.product_id is not None
    ]

    comparison = await compare_basket(
        db,
        product_ids,
        current_store=receipt.store_name,
    )

    return _build_response(
        comparisons=comparison.comparisons,
        total_items=comparison.total_items,
        matched_items=comparison.matched_items,
        cheapest_store=comparison.cheapest_store,
        cheapest_total=comparison.cheapest_total,
        current_total=comparison.current_total,
        savings=comparison.savings,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/prices/compare-list
# ---------------------------------------------------------------------------


@router.get("/compare-list", response_model=BasketComparisonResponse)
async def compare_list_prices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BasketComparisonResponse:
    """Compare current active shopping list across supermarket chains."""
    result = await db.execute(
        select(ListItem).where(
            ListItem.user_id == current_user.id,
            ListItem.status == "active",
        )
    )
    items = result.scalars().all()

    # Collect product IDs from items that have linked products
    product_ids = [
        item.product_id
        for item in items
        if item.product_id is not None
    ]

    comparison = await compare_basket(db, product_ids)

    return _build_response(
        comparisons=comparison.comparisons,
        total_items=len(items),
        matched_items=comparison.matched_items,
        cheapest_store=comparison.cheapest_store,
        cheapest_total=comparison.cheapest_total,
        current_total=comparison.current_total,
        savings=comparison.savings,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/prices/refresh
# ---------------------------------------------------------------------------


class PriceRefreshResponse(BaseModel):
    refreshed_count: int
    product_count: int


@router.post("/refresh", response_model=PriceRefreshResponse)
async def refresh_prices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PriceRefreshResponse:
    """Fetch fresh prices from SuperGET for all products in the user's active list."""
    settings = get_settings()
    if not settings.superget_api_key:
        return PriceRefreshResponse(refreshed_count=0, product_count=0)

    result = await db.execute(
        select(ListItem.product_id).where(
            ListItem.user_id == current_user.id,
            ListItem.status == "active",
            ListItem.product_id.isnot(None),
        ).distinct()
    )
    product_ids = [row[0] for row in result.all()]

    if not product_ids:
        return PriceRefreshResponse(refreshed_count=0, product_count=0)

    results = await fetch_prices_for_products(db, product_ids)
    refreshed = sum(1 for r in results if r.matched)

    await logger.ainfo(
        "prices_refreshed",
        user_id=str(current_user.id),
        product_count=len(product_ids),
        refreshed_count=refreshed,
    )

    return PriceRefreshResponse(
        refreshed_count=refreshed,
        product_count=len(product_ids),
    )
