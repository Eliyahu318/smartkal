"""Shopping list CRUD endpoints: add, view, update, delete items."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.category import Category
from app.models.list_item import ListItem, ListItemSource, ListItemStatus
from app.models.user import User
from app.services.categorizer import auto_categorize

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

router = APIRouter(prefix="/list", tags=["list"])


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


@router.post("/items", response_model=ListItemResponse, status_code=201)
async def add_item(
    body: AddItemRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Add a new item to the shopping list.

    If category_id is not provided, attempts auto-categorization via Claude API.
    """
    category_id = body.category_id

    # Validate category ownership if provided
    if category_id is not None:
        await _verify_category_ownership(db, category_id, current_user.id)

    # Auto-categorize if no category specified
    if category_id is None:
        category_id = await auto_categorize(db, current_user.id, body.name)

    item = ListItem(
        user_id=current_user.id,
        name=body.name,
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
        name=body.name,
        category_id=str(category_id) if category_id else None,
    )

    return ListItemResponse.model_validate(item)


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
        item.name = body.name
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
