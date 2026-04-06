"""Tests for US-024: Dashboard backend API.

Tests spending by category, spending by store, monthly trend endpoints,
and smart basket comparison with per-category recommendations.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

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
# GET /api/v1/dashboard/spending
# ---------------------------------------------------------------------------


class TestSpendingByCategory:
    """Test spending breakdown by category."""

    @pytest.mark.anyio
    async def test_spending_with_categories(self) -> None:
        """Returns spending grouped by category with percentages."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.all.return_value = [
            ("מוצרי חלב", Decimal("150.00")),
            ("ירקות", Decimal("100.00")),
            ("לחמים", Decimal("50.00")),
        ]
        mock_session.execute.return_value = mock_result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/dashboard/spending?period=month",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "month"
        assert data["total_spending"] == 300.0
        assert len(data["categories"]) == 3
        assert data["categories"][0]["category_name"] == "מוצרי חלב"
        assert data["categories"][0]["total"] == 150.0
        assert data["categories"][0]["percentage"] == 50.0

    @pytest.mark.anyio
    async def test_spending_empty(self) -> None:
        """No receipts in period returns zero total and empty categories."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute.return_value = mock_result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/dashboard/spending?period=month",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total_spending"] == 0.0
        assert data["categories"] == []

    @pytest.mark.anyio
    async def test_spending_week_period(self) -> None:
        """Week period parameter is accepted and passed through."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.all.return_value = [
            ("ירקות", Decimal("80.00")),
        ]
        mock_session.execute.return_value = mock_result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/dashboard/spending?period=week",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "week"
        assert len(data["categories"]) == 1

    @pytest.mark.anyio
    async def test_spending_year_period(self) -> None:
        """Year period parameter is accepted."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute.return_value = mock_result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/dashboard/spending?period=year",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "year"

    @pytest.mark.anyio
    async def test_spending_invalid_period(self) -> None:
        """Invalid period parameter returns 422."""
        mock_session = AsyncMock(spec=AsyncSession)
        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/dashboard/spending?period=invalid",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_spending_unmatched_products_grouped_as_other(self) -> None:
        """Purchases without categories are grouped under 'אחר'."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.all.return_value = [
            ("אחר", Decimal("200.00")),
            ("ירקות", Decimal("100.00")),
        ]
        mock_session.execute.return_value = mock_result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/dashboard/spending?period=month",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["categories"][0]["category_name"] == "אחר"
        assert data["categories"][0]["total"] == 200.0


# ---------------------------------------------------------------------------
# GET /api/v1/dashboard/stores
# ---------------------------------------------------------------------------


class TestSpendingByStore:
    """Test spending breakdown by store chain."""

    @pytest.mark.anyio
    async def test_stores_with_data(self) -> None:
        """Returns store spending with receipt counts and percentages."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.all.return_value = [
            ("רמי לוי", Decimal("500.00"), 5),
            ("שופרסל", Decimal("300.00"), 3),
            ("ויקטורי", Decimal("200.00"), 2),
        ]
        mock_session.execute.return_value = mock_result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/dashboard/stores",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total_spending"] == 1000.0
        assert len(data["stores"]) == 3
        assert data["stores"][0]["store_name"] == "רמי לוי"
        assert data["stores"][0]["total"] == 500.0
        assert data["stores"][0]["receipt_count"] == 5
        assert data["stores"][0]["percentage"] == 50.0

    @pytest.mark.anyio
    async def test_stores_empty(self) -> None:
        """No receipts returns empty stores list."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute.return_value = mock_result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/dashboard/stores",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total_spending"] == 0.0
        assert data["stores"] == []

    @pytest.mark.anyio
    async def test_stores_unknown_store_name(self) -> None:
        """Receipts with null store_name grouped under 'לא ידוע'."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.all.return_value = [
            ("לא ידוע", Decimal("100.00"), 2),
        ]
        mock_session.execute.return_value = mock_result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/dashboard/stores",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["stores"][0]["store_name"] == "לא ידוע"


# ---------------------------------------------------------------------------
# GET /api/v1/dashboard/trends
# ---------------------------------------------------------------------------


class TestSpendingTrends:
    """Test monthly spending trend endpoint."""

    @pytest.mark.anyio
    async def test_trends_with_data(self) -> None:
        """Returns monthly trend data ordered chronologically."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.all.return_value = [
            ("2026-01", Decimal("800.00")),
            ("2026-02", Decimal("950.00")),
            ("2026-03", Decimal("720.00")),
        ]
        mock_session.execute.return_value = mock_result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/dashboard/trends",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["months"]) == 3
        assert data["months"][0]["month"] == "2026-01"
        assert data["months"][0]["total"] == 800.0
        assert data["months"][2]["month"] == "2026-03"
        assert data["months"][2]["total"] == 720.0

    @pytest.mark.anyio
    async def test_trends_empty(self) -> None:
        """No receipts returns empty months list."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute.return_value = mock_result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/dashboard/trends",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["months"] == []

    @pytest.mark.anyio
    async def test_trends_single_month(self) -> None:
        """Single month of data works correctly."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.all.return_value = [
            ("2026-03", Decimal("1200.00")),
        ]
        mock_session.execute.return_value = mock_result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/dashboard/trends",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["months"]) == 1
        assert data["months"][0]["total"] == 1200.0


# ---------------------------------------------------------------------------
# GET /api/v1/dashboard/smart-basket
# ---------------------------------------------------------------------------


def _mock_list_item(
    product_id: uuid.UUID | None = None,
    category_name: str = "מוצרי חלב",
    status: str = "active",
) -> MagicMock:
    """Create a mock ListItem with an attached category."""
    item = MagicMock()
    item.product_id = product_id
    item.status = status
    item.user_id = FAKE_USER_ID
    if category_name:
        item.category = MagicMock()
        item.category.name = category_name
    else:
        item.category = None
    return item


class TestSmartBasket:
    """Test GET /api/v1/dashboard/smart-basket endpoint."""

    @pytest.mark.anyio
    @patch("app.api.v1.dashboard.compare_basket_by_category")
    @patch("app.api.v1.dashboard.compare_basket")
    @patch("app.api.v1.dashboard._get_latest_prices_by_product")
    async def test_smart_basket_with_data(
        self,
        mock_prices: AsyncMock,
        mock_compare: AsyncMock,
        mock_by_category: AsyncMock,
    ) -> None:
        """Returns store comparisons and category recommendations."""
        from app.services.basket_comparator import (
            BasketComparison,
            CategoryRecommendation,
            StoreBasket,
        )

        pid1 = uuid.uuid4()
        pid2 = uuid.uuid4()

        # Mock items returned by DB query
        items = [
            _mock_list_item(product_id=pid1, category_name="מוצרי חלב"),
            _mock_list_item(product_id=pid2, category_name="ירקות"),
        ]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = items
        mock_session.execute.return_value = mock_result

        # Mock price map
        price_map = {
            pid1: {"רמי לוי": Decimal("10.00"), "שופרסל": Decimal("12.00")},
            pid2: {"רמי לוי": Decimal("8.00"), "שופרסל": Decimal("7.00")},
        }
        mock_prices.return_value = price_map

        # Mock compare_basket result
        mock_compare.return_value = BasketComparison(
            comparisons=[
                StoreBasket(store_name="רמי לוי", total=Decimal("18.00"), matched_count=2),
                StoreBasket(store_name="שופרסל", total=Decimal("19.00"), matched_count=2),
            ],
            total_items=2,
            matched_items=2,
            cheapest_store="רמי לוי",
            cheapest_total=Decimal("18.00"),
            current_total=Decimal("19.00"),
            savings=Decimal("1.00"),
        )

        # Mock per-category recommendations
        mock_by_category.return_value = [
            CategoryRecommendation(
                category_name="מוצרי חלב",
                cheapest_store="רמי לוי",
                cheapest_total=Decimal("10.00"),
                savings=Decimal("2.00"),
            ),
            CategoryRecommendation(
                category_name="ירקות",
                cheapest_store="שופרסל",
                cheapest_total=Decimal("7.00"),
                savings=Decimal("1.00"),
            ),
        ]

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/dashboard/smart-basket",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()

        # Overall comparison
        assert data["cheapest_store"] == "רמי לוי"
        assert data["cheapest_total"] == 18.0
        assert data["savings"] == 1.0
        assert data["total_items"] == 2
        assert data["matched_items"] == 2
        assert len(data["comparisons"]) == 2
        assert data["comparisons"][0]["store_name"] == "רמי לוי"
        assert data["comparisons"][0]["total"] == 18.0
        assert data["comparisons"][0]["matched_count"] == 2

        # Coverage text
        assert data["coverage_text"] == "השוואה על כל 2 המוצרים"

        # Category recommendations
        assert len(data["category_recommendations"]) == 2
        assert data["category_recommendations"][0]["category_name"] == "מוצרי חלב"
        assert data["category_recommendations"][0]["cheapest_store"] == "רמי לוי"
        assert data["category_recommendations"][0]["savings"] == 2.0
        assert data["category_recommendations"][1]["category_name"] == "ירקות"
        assert data["category_recommendations"][1]["cheapest_store"] == "שופרסל"

        # Verify price_map was passed to both functions
        mock_compare.assert_called_once()
        _, kwargs = mock_compare.call_args
        assert kwargs["price_map"] is price_map

        mock_by_category.assert_called_once()
        _, kwargs = mock_by_category.call_args
        assert kwargs["price_map"] is price_map

    @pytest.mark.anyio
    @patch("app.api.v1.dashboard.compare_basket_by_category")
    @patch("app.api.v1.dashboard.compare_basket")
    @patch("app.api.v1.dashboard._get_latest_prices_by_product")
    async def test_smart_basket_empty_list(
        self,
        mock_prices: AsyncMock,
        mock_compare: AsyncMock,
        mock_by_category: AsyncMock,
    ) -> None:
        """No active list items returns empty response."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/dashboard/smart-basket",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total_items"] == 0
        assert data["matched_items"] == 0
        assert data["comparisons"] == []
        assert data["cheapest_store"] == ""
        assert data["category_recommendations"] == []

        # No service calls made
        mock_prices.assert_not_called()
        mock_compare.assert_not_called()
        mock_by_category.assert_not_called()

    @pytest.mark.anyio
    @patch("app.api.v1.dashboard.compare_basket_by_category")
    @patch("app.api.v1.dashboard.compare_basket")
    @patch("app.api.v1.dashboard._get_latest_prices_by_product")
    async def test_smart_basket_items_without_products(
        self,
        mock_prices: AsyncMock,
        mock_compare: AsyncMock,
        mock_by_category: AsyncMock,
    ) -> None:
        """Items without product_id are counted but not compared."""
        # 3 items, but only 1 has a product_id
        pid1 = uuid.uuid4()
        items = [
            _mock_list_item(product_id=pid1, category_name="מוצרי חלב"),
            _mock_list_item(product_id=None, category_name="ירקות"),
            _mock_list_item(product_id=None, category_name="לחמים"),
        ]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = items
        mock_session.execute.return_value = mock_result

        mock_prices.return_value = {
            pid1: {"רמי לוי": Decimal("10.00")},
        }

        from app.services.basket_comparator import (
            BasketComparison,
            StoreBasket,
        )

        mock_compare.return_value = BasketComparison(
            comparisons=[
                StoreBasket(store_name="רמי לוי", total=Decimal("10.00"), matched_count=1),
            ],
            total_items=1,
            matched_items=1,
            cheapest_store="רמי לוי",
            cheapest_total=Decimal("10.00"),
            current_total=Decimal("10.00"),
            savings=Decimal("0"),
        )
        mock_by_category.return_value = []

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/dashboard/smart-basket",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        # total_items counts ALL items, not just those with products
        assert data["total_items"] == 3
        assert data["matched_items"] == 1
        # Partial coverage text
        assert "1 מתוך 3" in data["coverage_text"]
        assert "33%" in data["coverage_text"]

    @pytest.mark.anyio
    @patch("app.api.v1.dashboard.compare_basket_by_category")
    @patch("app.api.v1.dashboard.compare_basket")
    @patch("app.api.v1.dashboard._get_latest_prices_by_product")
    async def test_smart_basket_items_without_category(
        self,
        mock_prices: AsyncMock,
        mock_compare: AsyncMock,
        mock_by_category: AsyncMock,
    ) -> None:
        """Items without a category are grouped under 'אחר'."""
        pid1 = uuid.uuid4()
        items = [
            _mock_list_item(product_id=pid1, category_name=""),
        ]
        # Set category to None to simulate uncategorized item
        items[0].category = None

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = items
        mock_session.execute.return_value = mock_result

        mock_prices.return_value = {}

        from app.services.basket_comparator import BasketComparison

        mock_compare.return_value = BasketComparison(total_items=1, matched_items=0)
        mock_by_category.return_value = []

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/dashboard/smart-basket",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200

        # Verify "אחר" was passed in the product_category_map
        call_args = mock_by_category.call_args
        # Second positional arg is product_category_map
        product_category_map = call_args[0][1]
        assert pid1 in product_category_map
        assert product_category_map[pid1] == "אחר"
