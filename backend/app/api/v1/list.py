"""Shopping list CRUD endpoints: add, view, update, delete, complete, activate, refresh."""

from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.category import Category
from app.models.list_item import ListItem, ListItemSource, ListItemStatus
from app.models.product import Product
from app.models.user import User
from app.services.categorizer import auto_categorize
from app.services.refresh_engine import activate_overdue_items, calculate_refresh_for_item

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

router = APIRouter(prefix="/list", tags=["list"])

# Invisible Unicode characters that can slip in from Hebrew keyboards / RTL editing
_INVISIBLE_RE = re.compile(
    r"[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff\u00ad\u034f\u061c\u180e]"
)


def _sanitize_name(raw: str) -> str:
    """Strip invisible Unicode chars, normalize to NFC, and trim whitespace."""
    cleaned = _INVISIBLE_RE.sub("", raw)
    cleaned = unicodedata.normalize("NFC", cleaned)
    return cleaned.strip()


# --- Request / Response schemas ---


class AddItemRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=500, description="Product name")
    quantity: str | None = Field(None, max_length=50, description="Quantity (e.g., '2', '1 kg')")
    category_id: uuid.UUID | None = Field(None, description="Category UUID; auto-categorized if omitted")


class UpdateItemRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=500)
    quantity: str | None = Field(None, max_length=50)
    note: str | None = Field(None, max_length=1000)
    category_id: uuid.UUID | None = None


class ListItemResponse(BaseModel):
    id: uuid.UUID
    name: str
    quantity: str | None
    note: str | None
    status: str
    category_id: uuid.UUID | None
    product_id: uuid.UUID | None
    source: str
    confidence: float | None
    display_order: int
    auto_refresh_days: int | None
    system_refresh_days: int | None
    next_refresh_at: datetime | None
    last_completed_at: datetime | None
    last_activated_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CategoryInfo(BaseModel):
    id: uuid.UUID
    name: str
    icon: str | None
    display_order: int

    model_config = {"from_attributes": True}


class CategoryGroup(BaseModel):
    category: CategoryInfo | None
    items: list[ListItemResponse]


class ListResponse(BaseModel):
    groups: list[CategoryGroup]
    total_active: int
    total_completed: int


class PreferencesRequest(BaseModel):
    auto_refresh_days: int | None = Field(
        None, ge=1, le=365, description="User override for refresh frequency in days"
    )


class RefreshResponse(BaseModel):
    activated_count: int
    activated_items: list[ListItemResponse]


class UpgradeItemRequest(BaseModel):
    precise_name: str = Field(
        ..., min_length=1, max_length=500,
        description="Precise product name from receipt (e.g., 'חלב תנובה 3% 1 ליטר')",
    )


class SuggestionItem(BaseModel):
    name: str
    category_id: uuid.UUID | None


class SuggestionsResponse(BaseModel):
    suggestions: list[SuggestionItem]


class BulkItemsRequest(BaseModel):
    item_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=100)


class BulkActionResponse(BaseModel):
    affected_count: int


# --- Helpers ---


async def _verify_category_ownership(
    db: AsyncSession,
    category_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Category:
    """Verify that the category belongs to the user."""
    result = await db.execute(
        select(Category).where(
            Category.id == category_id,
            Category.user_id == user_id,
        )
    )
    category = result.scalar_one_or_none()
    if category is None:
        raise ValidationError(
            message_he="הקטגוריה לא נמצאה או שאינה שייכת למשתמש",
            message_en="Category not found or does not belong to user",
        )
    return category


async def _get_user_item(
    db: AsyncSession,
    item_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ListItem:
    """Fetch a list item that belongs to the given user, or raise NotFoundError."""
    result = await db.execute(
        select(ListItem).where(
            ListItem.id == item_id,
            ListItem.user_id == user_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise NotFoundError(
            message_he="הפריט לא נמצא",
            message_en="List item not found",
        )
    return item


# --- Endpoints ---


@router.get("", response_model=ListResponse)
async def get_list(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Return all list items grouped by category (active and completed)."""
    # Fetch all items for the user
    items_result = await db.execute(
        select(ListItem)
        .where(ListItem.user_id == current_user.id)
        .order_by(ListItem.display_order, ListItem.created_at)
    )
    items = list(items_result.scalars().all())

    # Fetch all categories for the user
    cats_result = await db.execute(
        select(Category)
        .where(Category.user_id == current_user.id)
        .order_by(Category.display_order)
    )
    categories = list(cats_result.scalars().all())
    cat_map = {c.id: c for c in categories}

    # Group items by category_id
    groups_dict: dict[uuid.UUID | None, list[ListItem]] = {}
    for item in items:
        groups_dict.setdefault(item.category_id, []).append(item)

    # Build ordered response — categories with items first, then uncategorized
    groups: list[CategoryGroup] = []
    for cat in categories:
        cat_items = groups_dict.pop(cat.id, [])
        if cat_items:
            groups.append(CategoryGroup(
                category=CategoryInfo.model_validate(cat),
                items=[ListItemResponse.model_validate(i) for i in cat_items],
            ))

    # Uncategorized items (category_id is None or category not found)
    for cat_id, cat_items in groups_dict.items():
        cat_obj = cat_map.get(cat_id) if cat_id is not None else None
        groups.append(CategoryGroup(
            category=CategoryInfo.model_validate(cat_obj) if cat_obj else None,
            items=[ListItemResponse.model_validate(i) for i in cat_items],
        ))

    total_active = sum(1 for i in items if i.status == ListItemStatus.ACTIVE.value)
    total_completed = sum(1 for i in items if i.status == ListItemStatus.COMPLETED.value)

    return ListResponse(
        groups=groups,
        total_active=total_active,
        total_completed=total_completed,
    )


@router.get("/suggestions", response_model=SuggestionsResponse)
async def get_suggestions(
    q: str = Query("", min_length=0, max_length=200, description="Search query"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Return distinct item names from user's history for autocomplete.

    Searches completed and active items matching the query prefix.
    Returns up to 10 unique names ordered by most recently used.
    """
    query = (
        select(ListItem.name, ListItem.category_id)
        .where(ListItem.user_id == current_user.id)
        .order_by(ListItem.updated_at.desc())
    )

    if q:
        query = query.where(ListItem.name.ilike(f"%{q}%"))

    result = await db.execute(query)
    rows = result.all()

    # Deduplicate by name, keeping the first (most recent) occurrence
    seen: set[str] = set()
    suggestions: list[SuggestionItem] = []
    for name, category_id in rows:
        if name not in seen:
            seen.add(name)
            suggestions.append(SuggestionItem(name=name, category_id=category_id))
        if len(suggestions) >= 10:
            break

    return SuggestionsResponse(suggestions=suggestions)


@router.post("/items", response_model=ListItemResponse, status_code=201)
async def add_item(
    body: AddItemRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Add a new item to the shopping list.

    If category_id is not provided, attempts auto-categorization via Claude API.
    """
    name = _sanitize_name(body.name)
    if not name:
        raise ValidationError(
            message_he="שם המוצר ריק",
            message_en="Product name is empty after sanitization",
        )

    category_id = body.category_id

    # Validate category ownership if provided
    if category_id is not None:
        await _verify_category_ownership(db, category_id, current_user.id)

    # Auto-categorize if no category specified
    if category_id is None:
        category_id = await auto_categorize(db, current_user.id, name)

    item = ListItem(
        user_id=current_user.id,
        name=name,
        quantity=body.quantity,
        category_id=category_id,
        status=ListItemStatus.ACTIVE.value,
        source=ListItemSource.MANUAL.value,
    )
    db.add(item)
    await db.flush()

    await logger.ainfo(
        "item_added",
        item_id=str(item.id),
        name=name,
        category_id=str(category_id) if category_id else None,
    )

    return ListItemResponse.model_validate(item)


# --- Bulk endpoints (must be before /{item_id} routes) ---


@router.patch("/items/bulk/activate", response_model=BulkActionResponse)
async def bulk_activate_items(
    body: BulkItemsRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Activate completed items. If item_ids provided, activate those; otherwise activate all."""
    query = select(ListItem).where(
        ListItem.user_id == current_user.id,
        ListItem.status == ListItemStatus.COMPLETED.value,
    )
    if body and body.item_ids:
        query = query.where(ListItem.id.in_(body.item_ids))

    result = await db.execute(query)
    items = list(result.scalars().all())
    now = datetime.now(timezone.utc)

    for item in items:
        item.status = ListItemStatus.ACTIVE.value
        item.last_activated_at = now
        item.next_refresh_at = None

    await db.flush()
    await logger.ainfo("bulk_activate", count=len(items), user_id=str(current_user.id))
    return BulkActionResponse(affected_count=len(items))


@router.patch("/items/bulk/complete", response_model=BulkActionResponse)
async def bulk_complete_items(
    body: BulkItemsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Mark multiple active items as completed."""
    result = await db.execute(
        select(ListItem).where(
            ListItem.user_id == current_user.id,
            ListItem.status == ListItemStatus.ACTIVE.value,
            ListItem.id.in_(body.item_ids),
        )
    )
    items = list(result.scalars().all())
    now = datetime.now(timezone.utc)

    for item in items:
        item.status = ListItemStatus.COMPLETED.value
        item.last_completed_at = now

    await db.flush()
    await logger.ainfo("bulk_complete", count=len(items), user_id=str(current_user.id))
    return BulkActionResponse(affected_count=len(items))


@router.post("/items/bulk/delete", response_model=BulkActionResponse)
async def bulk_delete_items(
    body: BulkItemsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Permanently delete multiple items."""
    result = await db.execute(
        select(ListItem).where(
            ListItem.user_id == current_user.id,
            ListItem.id.in_(body.item_ids),
        )
    )
    items = list(result.scalars().all())

    for item in items:
        await db.delete(item)

    await db.flush()
    await logger.ainfo("bulk_delete", count=len(items), user_id=str(current_user.id))
    return BulkActionResponse(affected_count=len(items))


@router.put("/items/{item_id}", response_model=ListItemResponse)
async def update_item(
    item_id: uuid.UUID,
    body: UpdateItemRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update an existing list item's name, quantity, note, or category."""
    item = await _get_user_item(db, item_id, current_user.id)

    if body.name is not None:
        sanitized = _sanitize_name(body.name)
        if not sanitized:
            raise ValidationError(
                message_he="שם המוצר ריק",
                message_en="Product name is empty after sanitization",
            )
        item.name = sanitized
    if body.quantity is not None:
        item.quantity = body.quantity
    if body.note is not None:
        item.note = body.note
    if body.category_id is not None:
        await _verify_category_ownership(db, body.category_id, current_user.id)
        item.category_id = body.category_id

    await db.flush()

    await logger.ainfo("item_updated", item_id=str(item_id))

    return ListItemResponse.model_validate(item)


@router.delete("/items/{item_id}", status_code=204)
async def delete_item(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Permanently remove an item from the shopping list."""
    item = await _get_user_item(db, item_id, current_user.id)

    await db.delete(item)
    await db.flush()

    await logger.ainfo("item_deleted", item_id=str(item_id))


@router.patch("/items/{item_id}/complete", response_model=ListItemResponse)
async def complete_item(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Mark an item as completed.

    Sets status to completed, records last_completed_at, and calculates
    next_refresh_at based on purchase frequency history.
    """
    item = await _get_user_item(db, item_id, current_user.id)

    if item.status == ListItemStatus.COMPLETED.value:
        raise ValidationError(
            message_he="הפריט כבר סומן כהושלם",
            message_en="Item is already completed",
        )

    item.status = ListItemStatus.COMPLETED.value
    item.last_completed_at = datetime.now(timezone.utc)

    # Calculate refresh schedule
    system_days, confidence, next_refresh_at = await calculate_refresh_for_item(db, item)
    if system_days is not None:
        item.system_refresh_days = system_days
    if confidence is not None:
        item.confidence = confidence
    if next_refresh_at is not None:
        item.next_refresh_at = next_refresh_at

    await db.flush()

    await logger.ainfo(
        "item_completed",
        item_id=str(item_id),
        system_refresh_days=system_days,
        next_refresh_at=str(next_refresh_at) if next_refresh_at else None,
    )

    return ListItemResponse.model_validate(item)


@router.patch("/items/{item_id}/activate", response_model=ListItemResponse)
async def activate_item(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Reactivate a completed item.

    Sets status to active, records last_activated_at, and clears next_refresh_at.
    """
    item = await _get_user_item(db, item_id, current_user.id)

    if item.status == ListItemStatus.ACTIVE.value:
        raise ValidationError(
            message_he="הפריט כבר פעיל",
            message_en="Item is already active",
        )

    item.status = ListItemStatus.ACTIVE.value
    item.last_activated_at = datetime.now(timezone.utc)
    item.next_refresh_at = None

    await db.flush()

    await logger.ainfo("item_activated", item_id=str(item_id))

    return ListItemResponse.model_validate(item)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_items(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Check all completed items and activate any past their next_refresh_at."""
    activated = await activate_overdue_items(db, current_user.id)

    return RefreshResponse(
        activated_count=len(activated),
        activated_items=[ListItemResponse.model_validate(i) for i in activated],
    )


@router.patch("/items/{item_id}/preferences", response_model=ListItemResponse)
async def update_item_preferences(
    item_id: uuid.UUID,
    body: PreferencesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Set user override for auto-refresh frequency.

    When auto_refresh_days is set, it takes priority over system-calculated frequency
    with confidence 0.95. Set to null to clear the override.
    """
    item = await _get_user_item(db, item_id, current_user.id)

    item.auto_refresh_days = body.auto_refresh_days

    # If the item is completed and has a user override, recalculate next_refresh_at
    if item.status == ListItemStatus.COMPLETED.value and body.auto_refresh_days is not None:
        if item.last_completed_at is not None:
            item.next_refresh_at = item.last_completed_at + timedelta(
                days=body.auto_refresh_days
            )
            item.confidence = 0.95
    elif body.auto_refresh_days is None and item.status == ListItemStatus.COMPLETED.value:
        # Cleared override — recalculate from system data
        system_days, confidence, next_refresh_at = await calculate_refresh_for_item(db, item)
        if system_days is not None:
            item.system_refresh_days = system_days
            item.confidence = confidence
            item.next_refresh_at = next_refresh_at
        else:
            item.confidence = None
            item.next_refresh_at = None

    await db.flush()

    await logger.ainfo(
        "item_preferences_updated",
        item_id=str(item_id),
        auto_refresh_days=body.auto_refresh_days,
    )

    return ListItemResponse.model_validate(item)


@router.patch("/items/{item_id}/upgrade", response_model=ListItemResponse)
async def upgrade_item_name(
    item_id: uuid.UUID,
    body: UpgradeItemRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Upgrade a list item's generic name to a precise receipt name.

    Also updates the linked product's name if one exists.
    """
    from app.services.product_matcher import normalize_hebrew_name

    item = await _get_user_item(db, item_id, current_user.id)

    old_name = item.name
    item.name = body.precise_name

    # Update linked product name if exists
    if item.product_id is not None:
        result = await db.execute(
            select(Product).where(Product.id == item.product_id)
        )
        product = result.scalar_one_or_none()
        if product is not None:
            product.name = body.precise_name
            product.normalized_name = normalize_hebrew_name(body.precise_name)

    await db.flush()

    await logger.ainfo(
        "item_name_upgraded",
        item_id=str(item_id),
        old_name=old_name,
        new_name=body.precise_name,
    )

    return ListItemResponse.model_validate(item)
