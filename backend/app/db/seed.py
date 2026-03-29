"""Seed script for default categories.

Usage:
    python -m app.db.seed <user_id>

Seeds the 15 default Hebrew categories for a given user.
Can also be called programmatically via seed_categories_for_user().
"""

from __future__ import annotations

import asyncio
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.category import Category

DEFAULT_CATEGORIES: list[dict[str, str | int | bool]] = [
    {"name": "ירקות", "icon": "🥬", "display_order": 0, "is_default": True},
    {"name": "פירות", "icon": "🍎", "display_order": 1, "is_default": True},
    {"name": "מוצרי חלב", "icon": "🥛", "display_order": 2, "is_default": True},
    {"name": "בשר עופות ודגים", "icon": "🍗", "display_order": 3, "is_default": True},
    {"name": "לחמים", "icon": "🍞", "display_order": 4, "is_default": True},
    {"name": "קפואים", "icon": "🧊", "display_order": 5, "is_default": True},
    {"name": "שימורים ויבשים", "icon": "🥫", "display_order": 6, "is_default": True},
    {"name": "חטיפים ומתוקים", "icon": "🍫", "display_order": 7, "is_default": True},
    {"name": "משקאות", "icon": "🥤", "display_order": 8, "is_default": True},
    {"name": "ניקיון", "icon": "🧹", "display_order": 9, "is_default": True},
    {"name": "טיפוח", "icon": "🧴", "display_order": 10, "is_default": True},
    {"name": "תינוקות", "icon": "👶", "display_order": 11, "is_default": True},
    {"name": "חד-פעמי", "icon": "🍽️", "display_order": 12, "is_default": True},
    {"name": "תבלינים ורטבים", "icon": "🌶️", "display_order": 13, "is_default": True},
    {"name": "אחר", "icon": "📦", "display_order": 14, "is_default": True},
]


async def seed_categories_for_user(
    session: AsyncSession, user_id: uuid.UUID
) -> list[Category]:
    """Insert default categories for a user, skipping any that already exist.

    Returns the list of newly created Category objects.
    """
    existing = await session.execute(
        select(Category.name).where(Category.user_id == user_id)
    )
    existing_names: set[str] = {row[0] for row in existing}

    created: list[Category] = []
    for cat_data in DEFAULT_CATEGORIES:
        if cat_data["name"] in existing_names:
            continue
        category = Category(
            user_id=user_id,
            name=str(cat_data["name"]),
            icon=str(cat_data["icon"]),
            display_order=int(cat_data["display_order"]),
            is_default=bool(cat_data["is_default"]),
        )
        session.add(category)
        created.append(category)

    await session.flush()
    return created


async def _main(user_id_str: str) -> None:
    user_id = uuid.UUID(user_id_str)
    async with async_session_factory() as session:
        created = await seed_categories_for_user(session, user_id)
        await session.commit()
        print(f"Seeded {len(created)} categories for user {user_id}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m app.db.seed <user_id>")
        sys.exit(1)
    asyncio.run(_main(sys.argv[1]))
