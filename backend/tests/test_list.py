"""Tests for US-009: Shopping list CRUD backend."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

FAKE_USER_ID = uuid.uuid4()
FAKE_CATEGORY_ID = uuid.uuid4()
FAKE_ITEM_ID = uuid.uuid4()


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
    display_order: int = 0,
) -> MagicMock:
    cat = MagicMock()
    cat.id = cat_id or FAKE_CATEGORY_ID
    cat.user_id = user_id or FAKE_USER_ID
    cat.name = name
    cat.icon = None
    cat.display_order = display_order
    cat.is_default = True
    return cat


def _mock_list_item(
    item_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    name: str = "חלב",
    status: str = "active",
) -> MagicMock:
    now = datetime.now(timezone.utc)
    item = MagicMock()
    item.id = item_id or FAKE_ITEM_ID
    item.user_id = user_id or FAKE_USER_ID
    item.product_id = None
    item.category_id = category_id
    item.name = name
    item.quantity = None
    item.note = None
    item.status = status
    item.source = "manual"
    item.confidence = None
    item.display_order = 0
    item.auto_refresh_days = None
    item.system_refresh_days = None
    item.next_refresh_at = None
    item.last_completed_at = None
    item.last_activated_at = None
    item.created_at = now
    item.updated_at = now
    return item


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
# GET /api/v1/list — retrieve grouped items
# ---------------------------------------------------------------------------


class TestGetList:
    """Test retrieving the shopping list grouped by category."""

    @pytest.mark.anyio
    async def test_get_list_empty(self) -> None:
        """Empty list returns empty groups."""
        mock_session = AsyncMock(spec=AsyncSession)

        # First call: items query (empty)
        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = []

        # Second call: categories query (empty)
        cats_result = MagicMock()
        cats_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [items_result, cats_result]

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/list",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["groups"] == []
        assert data["total_active"] == 0
        assert data["total_completed"] == 0

    @pytest.mark.anyio
    async def test_get_list_with_items_grouped(self) -> None:
        """Items are returned grouped by category."""
        cat = _mock_category()
        item1 = _mock_list_item(name="עגבנייה", category_id=cat.id, status="active")
        item2 = _mock_list_item(
            item_id=uuid.uuid4(), name="מלפפון", category_id=cat.id, status="completed"
        )

        mock_session = AsyncMock(spec=AsyncSession)

        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = [item1, item2]

        cats_result = MagicMock()
        cats_result.scalars.return_value.all.return_value = [cat]

        mock_session.execute.side_effect = [items_result, cats_result]

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/list",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["groups"]) == 1
        assert data["groups"][0]["category"]["name"] == "ירקות"
        assert len(data["groups"][0]["items"]) == 2
        assert data["total_active"] == 1
        assert data["total_completed"] == 1

    @pytest.mark.anyio
    async def test_get_list_uncategorized_items(self) -> None:
        """Items without a category appear in a group with null category."""
        item = _mock_list_item(name="משהו", category_id=None, status="active")

        mock_session = AsyncMock(spec=AsyncSession)

        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = [item]

        cats_result = MagicMock()
        cats_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [items_result, cats_result]

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/list",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["groups"]) == 1
        assert data["groups"][0]["category"] is None
        assert data["groups"][0]["items"][0]["name"] == "משהו"

    @pytest.mark.anyio
    async def test_get_list_sorts_items_alphabetically(self) -> None:
        """Items within each category are returned sorted by name (Hebrew א-ב)."""
        cat = _mock_category()
        # Mock returns items in non-alphabetical order; the endpoint must sort them.
        items = [
            _mock_list_item(item_id=uuid.uuid4(), name="תפוז", category_id=cat.id),
            _mock_list_item(item_id=uuid.uuid4(), name="אבטיח", category_id=cat.id),
            _mock_list_item(item_id=uuid.uuid4(), name="מלפפון", category_id=cat.id),
            _mock_list_item(item_id=uuid.uuid4(), name="בננה", category_id=cat.id),
        ]
        # Pre-set canonical_key on every item so the lazy backfill is a no-op
        # and doesn't try to flush against the mock.
        for item in items:
            item.canonical_key = item.name

        mock_session = AsyncMock(spec=AsyncSession)
        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = items
        cats_result = MagicMock()
        cats_result.scalars.return_value.all.return_value = [cat]
        mock_session.execute.side_effect = [items_result, cats_result]

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/list",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        names = [i["name"] for i in data["groups"][0]["items"]]
        # Hebrew alphabetical order: אבטיח, בננה, מלפפון, תפוז
        assert names == ["אבטיח", "בננה", "מלפפון", "תפוז"]


# ---------------------------------------------------------------------------
# POST /api/v1/list/items — add item
# ---------------------------------------------------------------------------


class TestAddItem:
    """Test adding items to the shopping list."""

    @pytest.mark.anyio
    @patch("app.api.v1.list.auto_categorize", new_callable=AsyncMock)
    async def test_add_item_with_category(self, mock_categorize: AsyncMock) -> None:
        """Adding an item with explicit category_id skips auto-categorization."""
        cat = _mock_category()
        added_items: list[Any] = []

        mock_session = AsyncMock(spec=AsyncSession)

        # _verify_category_ownership query
        cat_result = MagicMock()
        cat_result.scalar_one_or_none.return_value = cat
        mock_session.execute.return_value = cat_result

        def capture_add(obj: Any) -> None:
            added_items.append(obj)
            obj.id = uuid.uuid4()
            obj.product_id = None
            obj.note = None
            obj.confidence = None
            obj.display_order = 0
            obj.auto_refresh_days = None
            obj.system_refresh_days = None
            obj.next_refresh_at = None
            obj.last_completed_at = None
            obj.last_activated_at = None
            obj.created_at = datetime.now(timezone.utc)
            obj.updated_at = datetime.now(timezone.utc)

        mock_session.add.side_effect = capture_add

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/list/items",
                json={"name": "חלב", "category_id": str(cat.id)},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "חלב"
        assert data["status"] == "active"
        assert data["source"] == "manual"
        mock_categorize.assert_not_called()

    @pytest.mark.anyio
    @patch("app.api.v1.list.auto_categorize", new_callable=AsyncMock)
    async def test_add_item_auto_categorized(self, mock_categorize: AsyncMock) -> None:
        """Adding an item without category_id triggers auto-categorization."""
        auto_cat_id = uuid.uuid4()
        mock_categorize.return_value = auto_cat_id
        added_items: list[Any] = []

        mock_session = AsyncMock(spec=AsyncSession)

        def capture_add(obj: Any) -> None:
            added_items.append(obj)
            obj.id = uuid.uuid4()
            obj.product_id = None
            obj.note = None
            obj.confidence = None
            obj.display_order = 0
            obj.auto_refresh_days = None
            obj.system_refresh_days = None
            obj.next_refresh_at = None
            obj.last_completed_at = None
            obj.last_activated_at = None
            obj.created_at = datetime.now(timezone.utc)
            obj.updated_at = datetime.now(timezone.utc)

        mock_session.add.side_effect = capture_add

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/list/items",
                json={"name": "עגבנייה"},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "עגבנייה"
        assert data["category_id"] == str(auto_cat_id)
        mock_categorize.assert_called_once()

    @pytest.mark.anyio
    async def test_add_item_empty_name_returns_422(self) -> None:
        """Empty name returns validation error."""
        mock_session = AsyncMock(spec=AsyncSession)
        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/list/items",
                json={"name": ""},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_add_item_wrong_category_returns_422(self) -> None:
        """Category that doesn't belong to user returns validation error."""
        mock_session = AsyncMock(spec=AsyncSession)

        # _verify_category_ownership returns None
        cat_result = MagicMock()
        cat_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = cat_result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/list/items",
                json={"name": "חלב", "category_id": str(uuid.uuid4())},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 422
        data = response.json()
        assert data["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.anyio
    @patch("app.api.v1.list.auto_categorize", new_callable=AsyncMock)
    async def test_add_item_with_quantity(self, mock_categorize: AsyncMock) -> None:
        """Item with quantity is stored correctly."""
        mock_categorize.return_value = None

        mock_session = AsyncMock(spec=AsyncSession)

        def capture_add(obj: Any) -> None:
            obj.id = uuid.uuid4()
            obj.product_id = None
            obj.note = None
            obj.confidence = None
            obj.display_order = 0
            obj.auto_refresh_days = None
            obj.system_refresh_days = None
            obj.next_refresh_at = None
            obj.last_completed_at = None
            obj.last_activated_at = None
            obj.created_at = datetime.now(timezone.utc)
            obj.updated_at = datetime.now(timezone.utc)

        mock_session.add.side_effect = capture_add

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/list/items",
                json={"name": "ביצים", "quantity": "12"},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["quantity"] == "12"


# ---------------------------------------------------------------------------
# PUT /api/v1/list/items/{id} — update item
# ---------------------------------------------------------------------------


class TestUpdateItem:
    """Test updating list items."""

    @pytest.mark.anyio
    async def test_update_item_name(self) -> None:
        """Update item name succeeds."""
        item = _mock_list_item()

        mock_session = AsyncMock(spec=AsyncSession)
        item_result = MagicMock()
        item_result.scalar_one_or_none.return_value = item
        mock_session.execute.return_value = item_result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.put(
                f"/api/v1/list/items/{item.id}",
                json={"name": "חלב תנובה 3%"},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        assert item.name == "חלב תנובה 3%"

    @pytest.mark.anyio
    async def test_update_item_category(self) -> None:
        """Update item category verifies ownership."""
        item = _mock_list_item()
        new_cat = _mock_category(cat_id=uuid.uuid4(), name="מוצרי חלב")

        mock_session = AsyncMock(spec=AsyncSession)

        # First execute: _get_user_item
        item_result = MagicMock()
        item_result.scalar_one_or_none.return_value = item

        # Second execute: _verify_category_ownership
        cat_result = MagicMock()
        cat_result.scalar_one_or_none.return_value = new_cat

        mock_session.execute.side_effect = [item_result, cat_result]

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.put(
                f"/api/v1/list/items/{item.id}",
                json={"category_id": str(new_cat.id)},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        assert item.category_id == new_cat.id

    @pytest.mark.anyio
    async def test_update_nonexistent_item_returns_404(self) -> None:
        """Updating a nonexistent item returns 404."""
        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.put(
                f"/api/v1/list/items/{uuid.uuid4()}",
                json={"name": "test"},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "NOT_FOUND"

    @pytest.mark.anyio
    async def test_update_item_note(self) -> None:
        """Update item note field."""
        item = _mock_list_item()

        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = item
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.put(
                f"/api/v1/list/items/{item.id}",
                json={"note": "לקנות את הגדול"},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        assert item.note == "לקנות את הגדול"


# ---------------------------------------------------------------------------
# DELETE /api/v1/list/items/{id} — delete item
# ---------------------------------------------------------------------------


class TestDeleteItem:
    """Test deleting list items."""

    @pytest.mark.anyio
    async def test_delete_item_succeeds(self) -> None:
        """Deleting an existing item returns 204."""
        item = _mock_list_item()

        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = item
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(
                f"/api/v1/list/items/{item.id}",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 204
        mock_session.delete.assert_called_once_with(item)

    @pytest.mark.anyio
    async def test_delete_nonexistent_item_returns_404(self) -> None:
        """Deleting a nonexistent item returns 404."""
        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(
                f"/api/v1/list/items/{uuid.uuid4()}",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# User isolation
# ---------------------------------------------------------------------------


class TestUserIsolation:
    """Verify that users cannot access each other's items."""

    @pytest.mark.anyio
    async def test_user_cannot_access_other_users_item(self) -> None:
        """Accessing another user's item returns 404 (scoped query returns None)."""
        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = None  # Item not found for this user
        mock_session.execute.return_value = result

        user = _mock_user(user_id=uuid.uuid4())  # Different user
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.put(
                f"/api/v1/list/items/{uuid.uuid4()}",
                json={"name": "hacked"},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Auto-categorization unit tests
# ---------------------------------------------------------------------------


class TestAutoCategorize:
    """Test the auto_categorize service function."""

    @pytest.mark.anyio
    @patch("app.services.categorizer.get_settings")
    async def test_no_api_key_returns_none(self, mock_settings: MagicMock) -> None:
        """When no API key is configured, returns None."""
        mock_settings.return_value = MagicMock(anthropic_api_key="")

        from app.services.categorizer import auto_categorize

        mock_session = AsyncMock(spec=AsyncSession)
        result = await auto_categorize(mock_session, FAKE_USER_ID, "חלב")
        assert result is None

    @pytest.mark.anyio
    @patch("app.services.categorizer.AsyncAnthropic")
    @patch("app.services.categorizer.get_settings")
    async def test_successful_categorization(
        self,
        mock_settings: MagicMock,
        mock_anthropic_cls: MagicMock,
    ) -> None:
        """Claude returns a valid category name → matched to user category."""
        mock_settings.return_value = MagicMock(anthropic_api_key="test-key")

        # Mock Claude response
        mock_text_block = MagicMock()
        mock_text_block.text = '{"category": "מוצרי חלב"}'
        mock_response = MagicMock()
        mock_response.content = [mock_text_block]

        mock_client = AsyncMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_cls.return_value = mock_client

        # Mock DB: categories query
        dairy_cat_id = uuid.uuid4()
        cat1 = MagicMock()
        cat1.name = "ירקות"
        cat1.id = uuid.uuid4()
        cat2 = MagicMock()
        cat2.name = "מוצרי חלב"
        cat2.id = dairy_cat_id

        mock_session = AsyncMock(spec=AsyncSession)
        cats_result = MagicMock()
        cats_result.scalars.return_value.all.return_value = [cat1, cat2]
        mock_session.execute.return_value = cats_result

        from app.services.categorizer import auto_categorize

        result = await auto_categorize(mock_session, FAKE_USER_ID, "חלב תנובה")
        assert result == dairy_cat_id

    @pytest.mark.anyio
    @patch("app.services.categorizer.AsyncAnthropic")
    @patch("app.services.categorizer.get_settings")
    async def test_claude_returns_invalid_json(
        self,
        mock_settings: MagicMock,
        mock_anthropic_cls: MagicMock,
    ) -> None:
        """Claude returns non-JSON → gracefully returns None."""
        mock_settings.return_value = MagicMock(anthropic_api_key="test-key")

        mock_text_block = MagicMock()
        mock_text_block.text = "I don't know what category this is"
        mock_response = MagicMock()
        mock_response.content = [mock_text_block]

        mock_client = AsyncMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_cls.return_value = mock_client

        cat = MagicMock()
        cat.name = "ירקות"
        cat.id = uuid.uuid4()

        mock_session = AsyncMock(spec=AsyncSession)
        cats_result = MagicMock()
        cats_result.scalars.return_value.all.return_value = [cat]
        mock_session.execute.return_value = cats_result

        from app.services.categorizer import auto_categorize

        result = await auto_categorize(mock_session, FAKE_USER_ID, "חלב")
        assert result is None

    @pytest.mark.anyio
    @patch("app.services.categorizer.AsyncAnthropic")
    @patch("app.services.categorizer.get_settings")
    async def test_claude_api_error_returns_none(
        self,
        mock_settings: MagicMock,
        mock_anthropic_cls: MagicMock,
    ) -> None:
        """Claude API failure → gracefully returns None."""
        mock_settings.return_value = MagicMock(anthropic_api_key="test-key")

        mock_client = AsyncMock()
        mock_client.messages.create.side_effect = Exception("API down")
        mock_anthropic_cls.return_value = mock_client

        cat = MagicMock()
        cat.name = "ירקות"
        cat.id = uuid.uuid4()

        mock_session = AsyncMock(spec=AsyncSession)
        cats_result = MagicMock()
        cats_result.scalars.return_value.all.return_value = [cat]
        mock_session.execute.return_value = cats_result

        from app.services.categorizer import auto_categorize

        result = await auto_categorize(mock_session, FAKE_USER_ID, "חלב")
        assert result is None


# ---------------------------------------------------------------------------
# Auth protection (no token)
# ---------------------------------------------------------------------------


class TestAuthProtection:
    """Verify all list endpoints require authentication."""

    @pytest.mark.anyio
    async def test_get_list_requires_auth(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/list")
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_add_item_requires_auth(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/list/items", json={"name": "test"}
            )
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_update_item_requires_auth(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.put(
                f"/api/v1/list/items/{uuid.uuid4()}", json={"name": "test"}
            )
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_delete_item_requires_auth(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(f"/api/v1/list/items/{uuid.uuid4()}")
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_suggestions_requires_auth(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/list/suggestions?q=חלב")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/list/suggestions — autocomplete
# ---------------------------------------------------------------------------


class TestSuggestions:
    """Test autocomplete suggestions endpoint."""

    @pytest.mark.anyio
    async def test_suggestions_returns_matching_items(self) -> None:
        """Suggestions returns distinct item names matching query."""
        cat_id = uuid.uuid4()

        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.all.return_value = [
            ("חלב תנובה 3%", cat_id),
            ("חלב שוקו", cat_id),
        ]
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/list/suggestions",
                params={"q": "חלב"},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["suggestions"]) == 2
        assert data["suggestions"][0]["name"] == "חלב תנובה 3%"
        assert data["suggestions"][1]["name"] == "חלב שוקו"

    @pytest.mark.anyio
    async def test_suggestions_empty_query(self) -> None:
        """Empty query returns empty suggestions (no DB query with empty q)."""
        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.all.return_value = []
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/list/suggestions",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["suggestions"], list)

    @pytest.mark.anyio
    async def test_suggestions_deduplicates_names(self) -> None:
        """Duplicate names are deduplicated, keeping the first occurrence."""
        cat_id = uuid.uuid4()

        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.all.return_value = [
            ("חלב", cat_id),
            ("חלב", None),  # duplicate name, different category
            ("חלב שוקו", cat_id),
        ]
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/list/suggestions",
                params={"q": "חלב"},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["suggestions"]) == 2
        names = [s["name"] for s in data["suggestions"]]
        assert names == ["חלב", "חלב שוקו"]


# ---------------------------------------------------------------------------
# Duplicate detection / merge endpoints
# ---------------------------------------------------------------------------


def _mock_dup_item(
    name: str, canonical_key: str, item_id: uuid.UUID | None = None
) -> MagicMock:
    item = _mock_list_item(item_id=item_id, name=name)
    item.canonical_key = canonical_key
    return item


class TestGetDuplicates:
    @pytest.mark.anyio
    async def test_returns_groups(self) -> None:
        """GET /list/duplicates returns canonical-key groups with > 1 item."""
        a1 = _mock_dup_item("עגבניות שרי", "עגבניות שרי", item_id=uuid.uuid4())
        a2 = _mock_dup_item(
            "עגבניות שרי פרימיום", "עגבניות שרי", item_id=uuid.uuid4()
        )
        b = _mock_dup_item("חלב 3%", "חלב 3%", item_id=uuid.uuid4())  # singleton

        mock_session = AsyncMock(spec=AsyncSession)
        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = [a1, a2, b]
        mock_session.execute.return_value = items_result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/list/duplicates",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["groups"]) == 1
        assert data["groups"][0]["canonical"] == "עגבניות שרי"
        assert len(data["groups"][0]["items"]) == 2

    @pytest.mark.anyio
    async def test_empty_when_no_duplicates(self) -> None:
        a = _mock_dup_item("חלב 3%", "חלב 3%")
        mock_session = AsyncMock(spec=AsyncSession)
        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = [a]
        mock_session.execute.return_value = items_result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/list/duplicates",
                headers={"Authorization": "Bearer fake"},
            )
        assert response.status_code == 200
        assert response.json() == {"groups": []}


class TestMergeEndpoint:
    @pytest.mark.anyio
    async def test_validates_target_in_sources(self) -> None:
        target_id = uuid.uuid4()

        mock_session = AsyncMock(spec=AsyncSession)
        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/list/merge",
                headers={"Authorization": "Bearer fake"},
                json={
                    "target_id": str(target_id),
                    "source_ids": [str(target_id), str(uuid.uuid4())],
                },
            )
        # ValidationError → 400 / 422 (depending on handler)
        assert response.status_code in (400, 422)

    @pytest.mark.anyio
    async def test_validates_empty_sources(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/list/merge",
                headers={"Authorization": "Bearer fake"},
                json={
                    "target_id": str(uuid.uuid4()),
                    "source_ids": [],
                },
            )
        # Pydantic min_length=1 → 422
        assert response.status_code in (400, 422)

    @pytest.mark.anyio
    async def test_target_not_owned_returns_404(self) -> None:
        """Trying to merge into an item you don't own returns 404."""
        mock_session = AsyncMock(spec=AsyncSession)
        # _load_owned_items returns empty -> NotFoundError
        target_result = MagicMock()
        target_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = target_result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/list/merge",
                headers={"Authorization": "Bearer fake"},
                json={
                    "target_id": str(uuid.uuid4()),
                    "source_ids": [str(uuid.uuid4())],
                },
            )
        assert response.status_code == 404


class TestAutoMerge:
    @pytest.mark.anyio
    async def test_auto_merge_no_groups(self) -> None:
        """Auto-merge with no duplicates returns zero counts."""
        mock_session = AsyncMock(spec=AsyncSession)
        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = items_result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/list/duplicates/auto-merge",
                headers={"Authorization": "Bearer fake"},
            )
        assert response.status_code == 200
        assert response.json() == {"merged_count": 0, "group_count": 0}
