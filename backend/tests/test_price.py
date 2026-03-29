"""Tests for US-023: Price comparison endpoints.

Tests basket calculation, partial coverage scenarios, receipt comparison,
and list comparison endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
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


def _mock_receipt(
    receipt_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    store_name: str = "רמי לוי",
    purchases: list[MagicMock] | None = None,
) -> MagicMock:
    receipt = MagicMock()
    receipt.id = receipt_id or uuid.uuid4()
    receipt.user_id = user_id or FAKE_USER_ID
    receipt.store_name = store_name
    receipt.purchases = purchases or []
    return receipt


def _mock_purchase(
    product_id: uuid.UUID | None = None,
    raw_name: str = "חלב",
) -> MagicMock:
    purchase = MagicMock()
    purchase.product_id = product_id
    purchase.raw_name = raw_name
    return purchase


def _mock_list_item(
    product_id: uuid.UUID | None = None,
    name: str = "חלב",
    status: str = "active",
) -> MagicMock:
    item = MagicMock()
    item.product_id = product_id
    item.name = name
    item.status = status
    item.user_id = FAKE_USER_ID
    return item


# ---------------------------------------------------------------------------
# Unit tests — basket_comparator.compare_basket
# ---------------------------------------------------------------------------


class TestBasketComparator:
    """Test the basket comparison service logic."""

    @pytest.mark.anyio
    async def test_empty_product_list(self) -> None:
        """Empty product list returns zero comparison."""
        from app.services.basket_comparator import compare_basket

        mock_db = AsyncMock(spec=AsyncSession)
        result = await compare_basket(mock_db, [])

        assert result.total_items == 0
        assert result.matched_items == 0
        assert result.comparisons == []

    @pytest.mark.anyio
    async def test_no_price_data(self) -> None:
        """Products with no price history return zero matches."""
        from app.services.basket_comparator import compare_basket

        mock_db = AsyncMock(spec=AsyncSession)
        # execute returns empty result set
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        product_ids = [uuid.uuid4(), uuid.uuid4()]
        result = await compare_basket(mock_db, product_ids)

        assert result.total_items == 2
        assert result.matched_items == 0
        assert result.comparisons == []

    @pytest.mark.anyio
    async def test_full_coverage_two_stores(self) -> None:
        """Two stores with prices for all products — cheapest ranked first."""
        from app.services.basket_comparator import compare_basket

        pid1 = uuid.uuid4()
        pid2 = uuid.uuid4()

        # Simulate DB result: rows of (product_id, store_name, price)
        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.all.return_value = [
            (pid1, "רמי לוי", Decimal("5.90")),
            (pid1, "שופרסל", Decimal("6.50")),
            (pid2, "רמי לוי", Decimal("12.00")),
            (pid2, "שופרסל", Decimal("11.50")),
        ]
        mock_db.execute.return_value = mock_result

        result = await compare_basket(mock_db, [pid1, pid2])

        assert result.total_items == 2
        assert result.matched_items == 2
        assert len(result.comparisons) == 2
        # רמי לוי: 5.90 + 12.00 = 17.90
        # שופרסל: 6.50 + 11.50 = 18.00
        assert result.comparisons[0].store_name == "רמי לוי"
        assert result.comparisons[0].total == Decimal("17.90")
        assert result.comparisons[1].store_name == "שופרסל"
        assert result.comparisons[1].total == Decimal("18.00")
        assert result.cheapest_store == "רמי לוי"
        assert result.cheapest_total == Decimal("17.90")
        # Savings: most expensive (18.00) - cheapest (17.90) = 0.10
        assert result.savings == Decimal("0.10")

    @pytest.mark.anyio
    async def test_partial_coverage(self) -> None:
        """Only some products have price data — coverage reflects partial match."""
        from app.services.basket_comparator import compare_basket

        pid1 = uuid.uuid4()
        pid2 = uuid.uuid4()
        pid3 = uuid.uuid4()

        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        # Only pid1 and pid2 have prices — pid3 has no price data
        mock_result.all.return_value = [
            (pid1, "רמי לוי", Decimal("10.00")),
            (pid2, "רמי לוי", Decimal("20.00")),
        ]
        mock_db.execute.return_value = mock_result

        result = await compare_basket(mock_db, [pid1, pid2, pid3])

        assert result.total_items == 3
        assert result.matched_items == 2
        assert len(result.comparisons) == 1
        assert result.comparisons[0].store_name == "רמי לוי"
        assert result.comparisons[0].matched_count == 2

    @pytest.mark.anyio
    async def test_current_store_savings(self) -> None:
        """When current_store is specified, savings calculated against that store."""
        from app.services.basket_comparator import compare_basket

        pid1 = uuid.uuid4()

        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.all.return_value = [
            (pid1, "רמי לוי", Decimal("10.00")),
            (pid1, "שופרסל", Decimal("15.00")),
        ]
        mock_db.execute.return_value = mock_result

        result = await compare_basket(mock_db, [pid1], current_store="שופרסל")

        assert result.cheapest_store == "רמי לוי"
        assert result.current_total == Decimal("15.00")
        assert result.savings == Decimal("5.00")


# ---------------------------------------------------------------------------
# Integration tests — compare-receipt endpoint
# ---------------------------------------------------------------------------


class TestCompareReceipt:
    """Test GET /api/v1/prices/compare-receipt/{id}."""

    @pytest.mark.anyio
    async def test_receipt_not_found(self) -> None:
        """Nonexistent receipt returns 404."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/prices/compare-receipt/{uuid.uuid4()}",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 404

    @pytest.mark.anyio
    @patch("app.api.v1.price.compare_basket")
    async def test_receipt_comparison(self, mock_compare: AsyncMock) -> None:
        """Receipt with purchases returns comparison data."""
        from app.services.basket_comparator import BasketComparison, StoreBasket

        pid1 = uuid.uuid4()
        pid2 = uuid.uuid4()
        receipt = _mock_receipt(
            purchases=[
                _mock_purchase(product_id=pid1),
                _mock_purchase(product_id=pid2),
                _mock_purchase(product_id=None),  # unmatched purchase
            ],
        )

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = receipt
        mock_session.execute.return_value = mock_result

        mock_compare.return_value = BasketComparison(
            comparisons=[
                StoreBasket(store_name="רמי לוי", total=Decimal("50.00"), matched_count=2),
                StoreBasket(store_name="שופרסל", total=Decimal("55.00"), matched_count=2),
            ],
            total_items=2,
            matched_items=2,
            cheapest_store="רמי לוי",
            cheapest_total=Decimal("50.00"),
            current_total=Decimal("55.00"),
            savings=Decimal("5.00"),
        )

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/prices/compare-receipt/{receipt.id}",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["cheapest_store"] == "רמי לוי"
        assert data["savings"] == 5.0
        assert len(data["comparisons"]) == 2
        assert data["total_items"] == 2
        assert data["matched_items"] == 2
        # Verify compare_basket was called with only matched product IDs
        call_args = mock_compare.call_args
        assert set(call_args[0][1]) == {pid1, pid2}
        assert call_args[1]["current_store"] == "רמי לוי"

    @pytest.mark.anyio
    @patch("app.api.v1.price.compare_basket")
    async def test_receipt_no_matched_purchases(self, mock_compare: AsyncMock) -> None:
        """Receipt with no matched purchases returns empty comparison."""
        from app.services.basket_comparator import BasketComparison

        receipt = _mock_receipt(
            purchases=[
                _mock_purchase(product_id=None),
                _mock_purchase(product_id=None),
            ],
        )

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = receipt
        mock_session.execute.return_value = mock_result

        mock_compare.return_value = BasketComparison(total_items=0)

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/prices/compare-receipt/{receipt.id}",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["comparisons"] == []
        assert data["savings"] == 0.0


# ---------------------------------------------------------------------------
# Integration tests — compare-list endpoint
# ---------------------------------------------------------------------------


class TestCompareList:
    """Test GET /api/v1/prices/compare-list."""

    @pytest.mark.anyio
    @patch("app.api.v1.price.compare_basket")
    async def test_list_comparison(self, mock_compare: AsyncMock) -> None:
        """Active list with linked products returns comparison."""
        from app.services.basket_comparator import BasketComparison, StoreBasket

        pid1 = uuid.uuid4()
        pid2 = uuid.uuid4()

        items = [
            _mock_list_item(product_id=pid1, name="חלב"),
            _mock_list_item(product_id=pid2, name="לחם"),
            _mock_list_item(product_id=None, name="ביצים"),  # no linked product
        ]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = items
        mock_session.execute.return_value = mock_result

        mock_compare.return_value = BasketComparison(
            comparisons=[
                StoreBasket(store_name="שופרסל", total=Decimal("30.00"), matched_count=2),
            ],
            total_items=2,
            matched_items=2,
            cheapest_store="שופרסל",
            cheapest_total=Decimal("30.00"),
            current_total=Decimal("30.00"),
            savings=Decimal("0"),
        )

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/prices/compare-list",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["cheapest_store"] == "שופרסל"
        assert data["total_items"] == 3  # total list items, not just linked
        assert data["matched_items"] == 2
        # Coverage text: partial match
        assert "3" in data["coverage_text"]
        assert "2" in data["coverage_text"]

    @pytest.mark.anyio
    @patch("app.api.v1.price.compare_basket")
    async def test_empty_list(self, mock_compare: AsyncMock) -> None:
        """Empty active list returns empty comparison."""
        from app.services.basket_comparator import BasketComparison

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        mock_compare.return_value = BasketComparison(total_items=0)

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/prices/compare-list",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["comparisons"] == []
        assert data["total_items"] == 0


# ---------------------------------------------------------------------------
# Coverage text tests
# ---------------------------------------------------------------------------


class TestCoverageText:
    """Test the Hebrew coverage text generation."""

    @pytest.mark.anyio
    @patch("app.api.v1.price.compare_basket")
    async def test_partial_coverage_text(self, mock_compare: AsyncMock) -> None:
        """Partial coverage shows correct Hebrew text with percentages."""
        from app.services.basket_comparator import BasketComparison, StoreBasket

        pid1 = uuid.uuid4()
        items = [
            _mock_list_item(product_id=pid1),
            _mock_list_item(product_id=None),
            _mock_list_item(product_id=None),
        ]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = items
        mock_session.execute.return_value = mock_result

        mock_compare.return_value = BasketComparison(
            comparisons=[StoreBasket(store_name="רמי לוי", total=Decimal("10"), matched_count=1)],
            total_items=1,
            matched_items=1,
            cheapest_store="רמי לוי",
            cheapest_total=Decimal("10"),
            current_total=Decimal("10"),
            savings=Decimal("0"),
        )

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/prices/compare-list",
                headers={"Authorization": "Bearer fake"},
            )

        data = response.json()
        # total_items=3 (all list items), matched_items=1 (from compare_basket)
        assert "1" in data["coverage_text"]
        assert "3" in data["coverage_text"]
        assert "33%" in data["coverage_text"]

    @pytest.mark.anyio
    @patch("app.api.v1.price.compare_basket")
    async def test_full_coverage_text(self, mock_compare: AsyncMock) -> None:
        """Full coverage shows simplified Hebrew text."""
        from app.services.basket_comparator import BasketComparison, StoreBasket

        pid1 = uuid.uuid4()
        items = [_mock_list_item(product_id=pid1)]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = items
        mock_session.execute.return_value = mock_result

        mock_compare.return_value = BasketComparison(
            comparisons=[StoreBasket(store_name="רמי לוי", total=Decimal("10"), matched_count=1)],
            total_items=1,
            matched_items=1,
            cheapest_store="רמי לוי",
            cheapest_total=Decimal("10"),
            current_total=Decimal("10"),
            savings=Decimal("0"),
        )

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/prices/compare-list",
                headers={"Authorization": "Bearer fake"},
            )

        data = response.json()
        assert "כל" in data["coverage_text"]
        assert "1" in data["coverage_text"]
