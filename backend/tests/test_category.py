"""Tests for US-011: Category management backend."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

FAKE_USER_ID = uuid.uuid4()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _make_test_app() -> Any:
    """Create a test FastAPI app with all routes and exception handlers."""
    from fastapi import FastAPI

    from app.api.v1 import api_v1_router
    from app.core.exception_handlers import register_exception_handlers

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(api_v1_router)
    return app


def _mock_user(user_id: uuid.UUID | None = None) -> MagicMock:
    user = MagicMock()
    user.id = user_id or FAKE_USER_ID
    user.email = "test@example.com"
    user.name = "Test User"
    user.is_active = True
    return user


def _mock_category(
    cat_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    name: str = "ירקות",
    icon: str | None = "🥬",
    display_order: int = 0,
    is_default: bool = True,
) -> MagicMock:
    now = datetime.now(timezone.utc)
    cat = MagicMock()
    cat.id = cat_id or uuid.uuid4()
    cat.user_id = user_id or FAKE_USER_ID
    cat.name = name
    cat.icon = icon
    cat.display_order = display_order
    cat.is_default = is_default
    cat.created_at = now
    cat.updated_at = now
    return cat


def _setup_app_with_mocks(
    mock_session: AsyncMock,
    mock_user: MagicMock,
) -> Any:
    """Wire up dependency overrides for a test app."""
    from app.db.session import get_db
    from app.dependencies import get_current_user

    app = _make_test_app()

    async def fake_get_db():  # type: ignore[no-untyped-def]
        yield mock_session

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = lambda: mock_user

    return app


# ---------------------------------------------------------------------------
# GET /api/v1/categories — list categories
# ---------------------------------------------------------------------------


class TestGetCategories:
    """Test listing categories for a user."""

    @pytest.mark.anyio
    async def test_get_categories_empty(self) -> None:
        """User with no categories returns empty list."""
        mock_session = AsyncMock(spec=AsyncSession)

        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/categories",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.anyio
    async def test_get_categories_returns_ordered(self) -> None:
        """Categories are returned in display_order."""
        cat1 = _mock_category(name="ירקות", display_order=0)
        cat2 = _mock_category(name="פירות", display_order=1, icon="🍎")

        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalars.return_value.all.return_value = [cat1, cat2]
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/categories",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "ירקות"
        assert data[1]["name"] == "פירות"
        assert data[1]["icon"] == "🍎"


# ---------------------------------------------------------------------------
# POST /api/v1/categories — create category
# ---------------------------------------------------------------------------


class TestCreateCategory:
    """Test creating a new category."""

    @pytest.mark.anyio
    async def test_create_category_succeeds(self) -> None:
        """Creating a category with unique name succeeds."""
        mock_session = AsyncMock(spec=AsyncSession)

        # First execute: duplicate check (none found)
        dup_result = MagicMock()
        dup_result.scalar_one_or_none.return_value = None

        # Second execute: max display_order
        order_result = MagicMock()
        order_result.scalar_one_or_none.return_value = 5

        mock_session.execute.side_effect = [dup_result, order_result]

        def capture_add(obj: Any) -> None:
            obj.id = uuid.uuid4()
            obj.created_at = datetime.now(timezone.utc)
            obj.updated_at = datetime.now(timezone.utc)

        mock_session.add.side_effect = capture_add

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/categories",
                json={"name": "קטגוריה חדשה", "icon": "🆕"},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "קטגוריה חדשה"
        assert data["icon"] == "🆕"
        assert data["display_order"] == 6
        assert data["is_default"] is False

    @pytest.mark.anyio
    async def test_create_category_no_existing_order(self) -> None:
        """First category gets display_order 0."""
        mock_session = AsyncMock(spec=AsyncSession)

        dup_result = MagicMock()
        dup_result.scalar_one_or_none.return_value = None

        order_result = MagicMock()
        order_result.scalar_one_or_none.return_value = None  # No categories yet

        mock_session.execute.side_effect = [dup_result, order_result]

        def capture_add(obj: Any) -> None:
            obj.id = uuid.uuid4()
            obj.created_at = datetime.now(timezone.utc)
            obj.updated_at = datetime.now(timezone.utc)

        mock_session.add.side_effect = capture_add

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/categories",
                json={"name": "ראשונה"},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 201
        assert response.json()["display_order"] == 0

    @pytest.mark.anyio
    async def test_create_category_duplicate_name_returns_422(self) -> None:
        """Duplicate category name returns validation error."""
        mock_session = AsyncMock(spec=AsyncSession)

        existing_cat = _mock_category(name="ירקות")
        dup_result = MagicMock()
        dup_result.scalar_one_or_none.return_value = existing_cat
        mock_session.execute.return_value = dup_result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/categories",
                json={"name": "ירקות"},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.anyio
    async def test_create_category_empty_name_returns_422(self) -> None:
        """Empty name returns validation error."""
        mock_session = AsyncMock(spec=AsyncSession)
        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/categories",
                json={"name": ""},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# PUT /api/v1/categories/{id} — update category
# ---------------------------------------------------------------------------


class TestUpdateCategory:
    """Test updating categories."""

    @pytest.mark.anyio
    async def test_update_category_name(self) -> None:
        """Renaming a category succeeds."""
        cat = _mock_category(name="ירקות")

        mock_session = AsyncMock(spec=AsyncSession)

        # First execute: _get_user_category
        cat_result = MagicMock()
        cat_result.scalar_one_or_none.return_value = cat

        # Second execute: duplicate name check
        dup_result = MagicMock()
        dup_result.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [cat_result, dup_result]

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.put(
                f"/api/v1/categories/{cat.id}",
                json={"name": "ירקות טריים"},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        assert cat.name == "ירקות טריים"

    @pytest.mark.anyio
    async def test_update_category_icon(self) -> None:
        """Changing icon only succeeds without name duplicate check."""
        cat = _mock_category(name="ירקות", icon="🥬")

        mock_session = AsyncMock(spec=AsyncSession)
        cat_result = MagicMock()
        cat_result.scalar_one_or_none.return_value = cat
        mock_session.execute.return_value = cat_result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.put(
                f"/api/v1/categories/{cat.id}",
                json={"icon": "🥦"},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        assert cat.icon == "🥦"

    @pytest.mark.anyio
    async def test_update_category_duplicate_name_returns_422(self) -> None:
        """Renaming to existing name returns validation error."""
        cat = _mock_category(name="ירקות")
        other_cat = _mock_category(name="פירות", cat_id=uuid.uuid4())

        mock_session = AsyncMock(spec=AsyncSession)

        cat_result = MagicMock()
        cat_result.scalar_one_or_none.return_value = cat

        dup_result = MagicMock()
        dup_result.scalar_one_or_none.return_value = other_cat  # Duplicate found

        mock_session.execute.side_effect = [cat_result, dup_result]

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.put(
                f"/api/v1/categories/{cat.id}",
                json={"name": "פירות"},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.anyio
    async def test_update_nonexistent_category_returns_404(self) -> None:
        """Updating a nonexistent category returns 404."""
        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.put(
                f"/api/v1/categories/{uuid.uuid4()}",
                json={"name": "test"},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# DELETE /api/v1/categories/{id} — delete category (moves items to אחר)
# ---------------------------------------------------------------------------


class TestDeleteCategory:
    """Test deleting categories and item reassignment."""

    @pytest.mark.anyio
    async def test_delete_category_moves_items_to_other(self) -> None:
        """Deleting a category moves items to 'אחר'."""
        cat_to_delete = _mock_category(name="ירקות")
        other_cat = _mock_category(name="אחר", icon="📦", display_order=14)

        mock_session = AsyncMock(spec=AsyncSession)

        # First execute: _get_user_category (finds the category to delete)
        cat_result = MagicMock()
        cat_result.scalar_one_or_none.return_value = cat_to_delete

        # Second execute: _get_or_create_other_category (finds "אחר")
        other_result = MagicMock()
        other_result.scalar_one_or_none.return_value = other_cat

        # Third execute: UPDATE ListItem SET category_id (bulk update)
        update_result = MagicMock()

        mock_session.execute.side_effect = [cat_result, other_result, update_result]

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(
                f"/api/v1/categories/{cat_to_delete.id}",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 204
        mock_session.delete.assert_called_once_with(cat_to_delete)
        # Verify the bulk update was executed (third call)
        assert mock_session.execute.call_count == 3

    @pytest.mark.anyio
    async def test_cannot_delete_other_category(self) -> None:
        """Cannot delete the 'אחר' category."""
        other_cat = _mock_category(name="אחר", icon="📦")

        mock_session = AsyncMock(spec=AsyncSession)
        cat_result = MagicMock()
        cat_result.scalar_one_or_none.return_value = other_cat
        mock_session.execute.return_value = cat_result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(
                f"/api/v1/categories/{other_cat.id}",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        mock_session.delete.assert_not_called()

    @pytest.mark.anyio
    async def test_delete_nonexistent_category_returns_404(self) -> None:
        """Deleting a nonexistent category returns 404."""
        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(
                f"/api/v1/categories/{uuid.uuid4()}",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_delete_creates_other_if_missing(self) -> None:
        """If 'אחר' doesn't exist, it's created during delete."""
        cat_to_delete = _mock_category(name="ירקות")

        mock_session = AsyncMock(spec=AsyncSession)

        # First execute: _get_user_category
        cat_result = MagicMock()
        cat_result.scalar_one_or_none.return_value = cat_to_delete

        # Second execute: _get_or_create_other_category — not found
        other_result = MagicMock()
        other_result.scalar_one_or_none.return_value = None

        # Third execute: UPDATE ListItem
        update_result = MagicMock()

        mock_session.execute.side_effect = [cat_result, other_result, update_result]

        # Capture the add call for the newly created "אחר" category
        added_objects: list[Any] = []

        def capture_add(obj: Any) -> None:
            added_objects.append(obj)
            obj.id = uuid.uuid4()

        mock_session.add.side_effect = capture_add

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(
                f"/api/v1/categories/{cat_to_delete.id}",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 204
        # Verify "אחר" was created
        assert len(added_objects) == 1
        assert added_objects[0].name == "אחר"


# ---------------------------------------------------------------------------
# POST /api/v1/categories/reorder — bulk reorder
# ---------------------------------------------------------------------------


class TestReorderCategories:
    """Test bulk reorder of categories."""

    @pytest.mark.anyio
    async def test_reorder_succeeds(self) -> None:
        """Reordering categories updates display_order."""
        cat1 = _mock_category(name="ירקות", display_order=0)
        cat2 = _mock_category(name="פירות", display_order=1)
        cat3 = _mock_category(name="משקאות", display_order=2)

        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalars.return_value.all.return_value = [cat1, cat2, cat3]
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        # Reorder: משקאות first, then ירקות, then פירות
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/categories/reorder",
                json={"category_ids": [str(cat3.id), str(cat1.id), str(cat2.id)]},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        # Verify order was updated
        assert cat3.display_order == 0
        assert cat1.display_order == 1
        assert cat2.display_order == 2

    @pytest.mark.anyio
    async def test_reorder_invalid_id_returns_422(self) -> None:
        """Reordering with an unknown ID returns validation error."""
        cat1 = _mock_category(name="ירקות", display_order=0)

        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalars.return_value.all.return_value = [cat1]
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/categories/reorder",
                json={"category_ids": [str(uuid.uuid4())]},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.anyio
    async def test_reorder_empty_list_returns_422(self) -> None:
        """Empty category_ids list returns validation error."""
        mock_session = AsyncMock(spec=AsyncSession)
        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/categories/reorder",
                json={"category_ids": []},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# User isolation
# ---------------------------------------------------------------------------


class TestCategoryUserIsolation:
    """Verify that users cannot access each other's categories."""

    @pytest.mark.anyio
    async def test_user_cannot_update_other_users_category(self) -> None:
        """Accessing another user's category returns 404."""
        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = None  # Not found for this user
        mock_session.execute.return_value = result

        user = _mock_user(user_id=uuid.uuid4())
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.put(
                f"/api/v1/categories/{uuid.uuid4()}",
                json={"name": "hacked"},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# New user gets default categories (already implemented in auth.py)
# ---------------------------------------------------------------------------


class TestNewUserDefaults:
    """Verify seed_categories_for_user works correctly."""

    @pytest.mark.anyio
    async def test_seed_creates_15_categories(self) -> None:
        """Seeding a user with no categories creates 15 defaults."""
        from app.db.seed import DEFAULT_CATEGORIES, seed_categories_for_user

        mock_session = AsyncMock(spec=AsyncSession)

        # No existing categories
        existing_result = MagicMock()
        existing_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.execute.return_value = existing_result

        user_id = uuid.uuid4()
        created = await seed_categories_for_user(mock_session, user_id)

        assert len(created) == 15
        assert mock_session.add.call_count == 15

        # Verify all default names are present
        created_names = {c.name for c in created}
        default_names = {str(d["name"]) for d in DEFAULT_CATEGORIES}
        assert created_names == default_names

    @pytest.mark.anyio
    async def test_seed_skips_existing(self) -> None:
        """Seeding skips categories that already exist."""
        from app.db.seed import seed_categories_for_user

        mock_session = AsyncMock(spec=AsyncSession)

        # Some categories already exist
        existing_result = MagicMock()
        existing_result.__iter__ = MagicMock(
            return_value=iter([("ירקות",), ("פירות",)])
        )
        mock_session.execute.return_value = existing_result

        user_id = uuid.uuid4()
        created = await seed_categories_for_user(mock_session, user_id)

        assert len(created) == 13  # 15 - 2 existing
        created_names = {c.name for c in created}
        assert "ירקות" not in created_names
        assert "פירות" not in created_names


# ---------------------------------------------------------------------------
# Auth protection (no token)
# ---------------------------------------------------------------------------


class TestCategoryAuthProtection:
    """Verify all category endpoints require authentication."""

    @pytest.mark.anyio
    async def test_get_categories_requires_auth(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/categories")
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_create_category_requires_auth(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/categories", json={"name": "test"}
            )
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_update_category_requires_auth(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.put(
                f"/api/v1/categories/{uuid.uuid4()}", json={"name": "test"}
            )
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_delete_category_requires_auth(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(f"/api/v1/categories/{uuid.uuid4()}")
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_reorder_categories_requires_auth(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/categories/reorder",
                json={"category_ids": [str(uuid.uuid4())]},
            )
        assert response.status_code == 401
