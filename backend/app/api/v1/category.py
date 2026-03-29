"""Category management endpoints: list, create, rename, reorder, delete."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.category import Category
from app.models.list_item import ListItem
from app.models.user import User

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

router = APIRouter(prefix="/categories", tags=["categories"])


# --- Request / Response schemas ---


class CreateCategoryRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Category name")
    icon: str | None = Field(None, max_length=50, description="Emoji icon")


class UpdateCategoryRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    icon: str | None = Field(None, max_length=50)


class ReorderRequest(BaseModel):
    category_ids: list[uuid.UUID] = Field(
        ..., min_length=1, description="Ordered list of category IDs"
    )


class CategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    icon: str | None
    display_order: int
    is_default: bool
    created_at: Any
    updated_at: Any

    model_config = {"from_attributes": True}


# --- Helpers ---


async def _get_user_category(
    db: AsyncSession,
    category_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Category:
    """Fetch a category that belongs to the given user, or raise NotFoundError."""
    result = await db.execute(
        select(Category).where(
            Category.id == category_id,
            Category.user_id == user_id,
        )
    )
    category = result.scalar_one_or_none()
    if category is None:
        raise NotFoundError(
            message_he="הקטגוריה לא נמצאה",
            message_en="Category not found",
        )
    return category


async def _get_or_create_other_category(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> Category:
    """Find the 'אחר' category for a user, or create it if missing."""
    result = await db.execute(
        select(Category).where(
            Category.user_id == user_id,
            Category.name == "אחר",
        )
    )
    other_cat = result.scalar_one_or_none()
    if other_cat is not None:
        return other_cat

    # Create the "אחר" category
    other_cat = Category(
        user_id=user_id,
        name="אחר",
        icon="📦",
        display_order=999,
        is_default=True,
    )
    db.add(other_cat)
    await db.flush()
    return other_cat


# --- Endpoints ---


@router.get("", response_model=list[CategoryResponse])
async def get_categories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Return all categories for the current user, ordered by display_order."""
    result = await db.execute(
        select(Category)
        .where(Category.user_id == current_user.id)
        .order_by(Category.display_order)
    )
    categories = list(result.scalars().all())
    return [CategoryResponse.model_validate(c) for c in categories]


@router.post("", response_model=CategoryResponse, status_code=201)
async def create_category(
    body: CreateCategoryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new category for the current user."""
    # Check for duplicate name
    result = await db.execute(
        select(Category).where(
            Category.user_id == current_user.id,
            Category.name == body.name,
        )
    )
    if result.scalar_one_or_none() is not None:
        raise ValidationError(
            message_he="קטגוריה עם שם זה כבר קיימת",
            message_en="A category with this name already exists",
        )

    # Get max display_order for the user
    order_result = await db.execute(
        select(Category.display_order)
        .where(Category.user_id == current_user.id)
        .order_by(Category.display_order.desc())
        .limit(1)
    )
    max_order_row = order_result.scalar_one_or_none()
    next_order = (max_order_row + 1) if max_order_row is not None else 0

    category = Category(
        user_id=current_user.id,
        name=body.name,
        icon=body.icon,
        display_order=next_order,
        is_default=False,
    )
    db.add(category)
    await db.flush()

    await logger.ainfo(
        "category_created",
        category_id=str(category.id),
        name=body.name,
    )

    return CategoryResponse.model_validate(category)


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: uuid.UUID,
    body: UpdateCategoryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Rename a category or change its icon."""
    category = await _get_user_category(db, category_id, current_user.id)

    if body.name is not None:
        # Check for duplicate name (excluding self)
        dup_result = await db.execute(
            select(Category).where(
                Category.user_id == current_user.id,
                Category.name == body.name,
                Category.id != category_id,
            )
        )
        if dup_result.scalar_one_or_none() is not None:
            raise ValidationError(
                message_he="קטגוריה עם שם זה כבר קיימת",
                message_en="A category with this name already exists",
            )
        category.name = body.name

    if body.icon is not None:
        category.icon = body.icon

    await db.flush()

    await logger.ainfo("category_updated", category_id=str(category_id))

    return CategoryResponse.model_validate(category)


@router.delete("/{category_id}", status_code=204)
async def delete_category(
    category_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a category and move its items to 'אחר'.

    Cannot delete the 'אחר' category itself.
    """
    category = await _get_user_category(db, category_id, current_user.id)

    if category.name == "אחר":
        raise ValidationError(
            message_he="לא ניתן למחוק את קטגוריית 'אחר'",
            message_en="Cannot delete the 'אחר' category",
        )

    # Find or create the "אחר" category to reassign items
    other_cat = await _get_or_create_other_category(db, current_user.id)

    # Move all items from the deleted category to "אחר"
    await db.execute(
        update(ListItem)
        .where(
            ListItem.category_id == category_id,
            ListItem.user_id == current_user.id,
        )
        .values(category_id=other_cat.id)
    )

    await db.delete(category)
    await db.flush()

    await logger.ainfo(
        "category_deleted",
        category_id=str(category_id),
        items_moved_to="אחר",
    )


@router.post("/reorder", response_model=list[CategoryResponse])
async def reorder_categories(
    body: ReorderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Bulk reorder categories by passing an ordered array of IDs.

    Each category's display_order is set to its index in the array.
    """
    # Fetch all user's categories
    result = await db.execute(
        select(Category).where(Category.user_id == current_user.id)
    )
    categories = list(result.scalars().all())
    cat_map = {c.id: c for c in categories}

    # Validate all IDs belong to the user
    for cid in body.category_ids:
        if cid not in cat_map:
            raise ValidationError(
                message_he="אחת או יותר מהקטגוריות לא נמצאו",
                message_en="One or more category IDs not found",
                details={"invalid_id": str(cid)},
            )

    # Update display_order for each category
    for idx, cid in enumerate(body.category_ids):
        cat_map[cid].display_order = idx

    await db.flush()

    await logger.ainfo(
        "categories_reordered",
        count=len(body.category_ids),
    )

    # Return in new order
    ordered = sorted(categories, key=lambda c: c.display_order)
    return [CategoryResponse.model_validate(c) for c in ordered]
