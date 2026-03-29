"""Tests for US-022: SuperGET API client and product matching."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.price_comparator import (
    SUPERGET_BASE_URL,
    ProductPriceResult,
    StorePrice,
    _parse_store_prices,
    _safe_decimal,
    _superget_request,
    fetch_and_save_prices,
    fetch_prices_for_products,
    get_prices_for_product,
    save_prices_to_history,
    search_product_by_barcode,
    search_product_by_name,
)


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

FAKE_PRODUCT_ID = uuid.uuid4()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _mock_product(
    product_id: uuid.UUID | None = None,
    name: str = "חלב תנובה 3%",
    barcode: str | None = "7290000001234",
    normalized_name: str = "חלב תנובה 3",
) -> MagicMock:
    product = MagicMock()
    product.id = product_id or FAKE_PRODUCT_ID
    product.name = name
    product.barcode = barcode
    product.normalized_name = normalized_name
    return product


def _make_superget_response(
    items: list[dict[str, object]] | None = None,
    status: str = "ok",
) -> dict[str, object]:
    """Build a mock SuperGET API response."""
    return {
        "status": status,
        "data": items or [],
    }


def _make_store_item(
    chain_name: str = "שופרסל",
    branch_name: str | None = "רחובות",
    price: float = 6.90,
    item_name: str = "חלב תנובה 3% 1 ליטר",
    barcode: str = "7290000001234",
) -> dict[str, object]:
    return {
        "chain_name": chain_name,
        "branch_name": branch_name,
        "price": price,
        "item_name": item_name,
        "barcode": barcode,
    }


# ---------------------------------------------------------------------------
# Unit tests: _safe_decimal
# ---------------------------------------------------------------------------


class TestSafeDecimal:
    def test_valid_number(self) -> None:
        assert _safe_decimal(6.90) == Decimal("6.9")

    def test_valid_string(self) -> None:
        assert _safe_decimal("12.50") == Decimal("12.50")

    def test_none(self) -> None:
        assert _safe_decimal(None) is None

    def test_invalid_string(self) -> None:
        assert _safe_decimal("not-a-number") is None

    def test_zero(self) -> None:
        assert _safe_decimal(0) == Decimal("0")


# ---------------------------------------------------------------------------
# Unit tests: _parse_store_prices
# ---------------------------------------------------------------------------


class TestParseStorePrices:
    def test_parses_valid_data_key(self) -> None:
        response = _make_superget_response([
            _make_store_item("שופרסל", "רחובות", 6.90),
            _make_store_item("רמי לוי", "מודיעין", 5.90),
        ])
        prices = _parse_store_prices(response, "חלב")
        assert len(prices) == 2
        assert prices[0].store_name == "שופרסל"
        assert prices[0].price == Decimal("6.9")
        assert prices[1].store_name == "רמי לוי"
        assert prices[1].price == Decimal("5.9")

    def test_parses_results_key(self) -> None:
        response = {"status": "ok", "results": [_make_store_item()]}
        prices = _parse_store_prices(response, "חלב")
        assert len(prices) == 1

    def test_parses_items_key(self) -> None:
        response = {"status": "ok", "items": [_make_store_item()]}
        prices = _parse_store_prices(response, "חלב")
        assert len(prices) == 1

    def test_skips_invalid_price(self) -> None:
        response = _make_superget_response([
            {**_make_store_item(), "price": None},
            {**_make_store_item(), "price": -5},
        ])
        prices = _parse_store_prices(response, "חלב")
        assert len(prices) == 0

    def test_skips_missing_store_name(self) -> None:
        item = _make_store_item()
        item.pop("chain_name")
        item["store_name"] = ""
        response = _make_superget_response([item])
        prices = _parse_store_prices(response, "חלב")
        assert len(prices) == 0

    def test_empty_data(self) -> None:
        response = _make_superget_response([])
        prices = _parse_store_prices(response, "חלב")
        assert len(prices) == 0

    def test_no_data_key(self) -> None:
        response: dict[str, object] = {"status": "ok"}
        prices = _parse_store_prices(response, "חלב")
        assert len(prices) == 0

    def test_branch_name_optional(self) -> None:
        response = _make_superget_response([
            _make_store_item(branch_name=None),
        ])
        prices = _parse_store_prices(response, "חלב")
        assert len(prices) == 1
        assert prices[0].store_branch is None

    def test_alternative_price_field(self) -> None:
        """SuperGET may use 'item_price' instead of 'price'."""
        item: dict[str, object] = {
            "chain_name": "שופרסל",
            "item_price": 7.50,
            "item_name": "לחם",
        }
        response = _make_superget_response([item])
        prices = _parse_store_prices(response, "לחם")
        assert len(prices) == 1
        assert prices[0].price == Decimal("7.5")


# ---------------------------------------------------------------------------
# Async tests: _superget_request
# ---------------------------------------------------------------------------


class TestSupergetRequest:
    @pytest.mark.anyio
    @patch("app.services.price_comparator.get_settings")
    async def test_missing_api_key_raises(self, mock_settings: MagicMock) -> None:
        mock_settings.return_value.superget_api_key = ""
        with pytest.raises(Exception, match="SuperGET API key not configured"):
            await _superget_request("TestAction")

    @pytest.mark.anyio
    @patch("app.services.price_comparator.get_settings")
    async def test_successful_request(self, mock_settings: MagicMock) -> None:
        mock_settings.return_value.superget_api_key = "test-key-123"

        mock_response = httpx.Response(
            200,
            json={"status": "ok", "data": [{"price": 5}]},
            request=httpx.Request("POST", SUPERGET_BASE_URL),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await _superget_request("SearchProduct", {"product_name": "חלב"})

        assert result["status"] == "ok"
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs.args[1] if len(call_kwargs.args) > 1 else call_kwargs.kwargs.get("json")
        # Verify the payload contains action, api_key, and extra params
        assert payload["action"] == "SearchProduct"
        assert payload["api_key"] == "test-key-123"
        assert payload["product_name"] == "חלב"

    @pytest.mark.anyio
    @patch("app.services.price_comparator.get_settings")
    async def test_api_error_status_raises(self, mock_settings: MagicMock) -> None:
        mock_settings.return_value.superget_api_key = "test-key"

        mock_response = httpx.Response(
            200,
            json={"status": "error", "message": "Invalid barcode"},
            request=httpx.Request("POST", SUPERGET_BASE_URL),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            with pytest.raises(Exception, match="SuperGET API error"):
                await _superget_request("SearchByBarcode", {"barcode": "invalid"})

    @pytest.mark.anyio
    @patch("app.services.price_comparator.get_settings")
    async def test_network_error_retries_and_raises(self, mock_settings: MagicMock) -> None:
        mock_settings.return_value.superget_api_key = "test-key"

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection refused")
            with pytest.raises(Exception, match="SuperGET API failed after"):
                await _superget_request("TestAction")
            # Should retry: 1 initial + MAX_RETRIES
            assert mock_post.call_count == 2  # 1 + MAX_RETRIES(1)

    @pytest.mark.anyio
    @patch("app.services.price_comparator.get_settings")
    async def test_http_error_retries(self, mock_settings: MagicMock) -> None:
        mock_settings.return_value.superget_api_key = "test-key"

        error_response = httpx.Response(
            500,
            request=httpx.Request("POST", SUPERGET_BASE_URL),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = error_response
            with pytest.raises(Exception, match="SuperGET API failed after"):
                await _superget_request("TestAction")
            assert mock_post.call_count == 2


# ---------------------------------------------------------------------------
# Async tests: search functions
# ---------------------------------------------------------------------------


class TestSearchFunctions:
    @pytest.mark.anyio
    async def test_search_by_barcode(self) -> None:
        mock_data = _make_superget_response([
            _make_store_item("שופרסל", "רחובות", 6.90, barcode="7290000001234"),
        ])
        with patch("app.services.price_comparator._superget_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_data
            prices = await search_product_by_barcode("7290000001234")

        assert len(prices) == 1
        assert prices[0].store_name == "שופרסל"
        mock_req.assert_called_once_with("SearchByBarcode", {"barcode": "7290000001234"})

    @pytest.mark.anyio
    async def test_search_by_name(self) -> None:
        mock_data = _make_superget_response([
            _make_store_item("רמי לוי", "מודיעין", 5.90, item_name="חלב תנובה 3%"),
        ])
        with patch("app.services.price_comparator._superget_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_data
            prices = await search_product_by_name("חלב תנובה 3%")

        assert len(prices) == 1
        assert prices[0].store_name == "רמי לוי"


# ---------------------------------------------------------------------------
# Async tests: get_prices_for_product
# ---------------------------------------------------------------------------


class TestGetPricesForProduct:
    @pytest.mark.anyio
    async def test_barcode_match_first(self) -> None:
        product = _mock_product(barcode="7290000001234")
        barcode_prices = [
            StorePrice("שופרסל", "רחובות", Decimal("6.90"), "חלב", "7290000001234"),
        ]

        with patch(
            "app.services.price_comparator.search_product_by_barcode",
            new_callable=AsyncMock,
        ) as mock_barcode:
            mock_barcode.return_value = barcode_prices
            prices = await get_prices_for_product(product)

        assert len(prices) == 1
        assert prices[0].store_name == "שופרסל"

    @pytest.mark.anyio
    async def test_fallback_to_name_when_barcode_empty(self) -> None:
        product = _mock_product(barcode=None)
        name_prices = [
            StorePrice("רמי לוי", None, Decimal("5.50"), "חלב תנובה 3%"),
        ]

        with patch(
            "app.services.price_comparator.search_product_by_name",
            new_callable=AsyncMock,
        ) as mock_name:
            mock_name.return_value = name_prices
            prices = await get_prices_for_product(product)

        assert len(prices) == 1
        assert prices[0].store_name == "רמי לוי"

    @pytest.mark.anyio
    async def test_fallback_to_name_when_barcode_fails(self) -> None:
        product = _mock_product(barcode="7290000001234")
        from app.core.errors import SuperGETError

        name_prices = [
            StorePrice("יוחננוף", None, Decimal("7.00"), "חלב תנובה 3%"),
        ]

        with (
            patch(
                "app.services.price_comparator.search_product_by_barcode",
                new_callable=AsyncMock,
                side_effect=SuperGETError(message_en="Barcode not found"),
            ),
            patch(
                "app.services.price_comparator.search_product_by_name",
                new_callable=AsyncMock,
                return_value=name_prices,
            ),
        ):
            prices = await get_prices_for_product(product)

        assert len(prices) == 1
        assert prices[0].store_name == "יוחננוף"

    @pytest.mark.anyio
    async def test_fallback_to_name_when_barcode_returns_empty(self) -> None:
        product = _mock_product(barcode="0000000000000")
        name_prices = [
            StorePrice("שופרסל", None, Decimal("8.00"), "חלב"),
        ]

        with (
            patch(
                "app.services.price_comparator.search_product_by_barcode",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.services.price_comparator.search_product_by_name",
                new_callable=AsyncMock,
                return_value=name_prices,
            ),
        ):
            prices = await get_prices_for_product(product)

        assert len(prices) == 1

    @pytest.mark.anyio
    async def test_both_fail_returns_empty(self) -> None:
        product = _mock_product(barcode="7290000001234")
        from app.core.errors import SuperGETError

        with (
            patch(
                "app.services.price_comparator.search_product_by_barcode",
                new_callable=AsyncMock,
                side_effect=SuperGETError(message_en="fail"),
            ),
            patch(
                "app.services.price_comparator.search_product_by_name",
                new_callable=AsyncMock,
                side_effect=SuperGETError(message_en="fail"),
            ),
        ):
            prices = await get_prices_for_product(product)

        assert prices == []


# ---------------------------------------------------------------------------
# Async tests: save_prices_to_history
# ---------------------------------------------------------------------------


class TestSavePricesToHistory:
    @pytest.mark.anyio
    async def test_saves_new_prices(self) -> None:
        db = AsyncMock()
        # No existing record
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        prices = [
            StorePrice("שופרסל", "רחובות", Decimal("6.90"), "חלב", "123"),
            StorePrice("רמי לוי", "מודיעין", Decimal("5.90"), "חלב", "123"),
        ]

        count = await save_prices_to_history(db, FAKE_PRODUCT_ID, prices)

        assert count == 2
        assert db.add.call_count == 2
        db.flush.assert_called_once()

    @pytest.mark.anyio
    async def test_skips_recent_existing_price(self) -> None:
        db = AsyncMock()

        # Existing recent record
        existing = MagicMock()
        existing.observed_at = datetime.now(timezone.utc)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        db.execute.return_value = mock_result

        prices = [
            StorePrice("שופרסל", "רחובות", Decimal("6.90"), "חלב"),
        ]

        count = await save_prices_to_history(db, FAKE_PRODUCT_ID, prices)

        assert count == 0
        db.add.assert_not_called()

    @pytest.mark.anyio
    async def test_empty_prices_list(self) -> None:
        db = AsyncMock()
        count = await save_prices_to_history(db, FAKE_PRODUCT_ID, [])
        assert count == 0
        db.flush.assert_not_called()


# ---------------------------------------------------------------------------
# Async tests: fetch_and_save_prices (integration)
# ---------------------------------------------------------------------------


class TestFetchAndSavePrices:
    @pytest.mark.anyio
    async def test_successful_fetch_and_save(self) -> None:
        product = _mock_product()
        db = AsyncMock()

        prices = [
            StorePrice("שופרסל", None, Decimal("6.90"), "חלב", "123"),
        ]

        # No existing price record
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        with patch(
            "app.services.price_comparator.get_prices_for_product",
            new_callable=AsyncMock,
            return_value=prices,
        ):
            result = await fetch_and_save_prices(db, product)

        assert result.matched is True
        assert len(result.prices) == 1
        assert result.product_id == product.id

    @pytest.mark.anyio
    async def test_api_failure_returns_empty_result(self) -> None:
        product = _mock_product()
        db = AsyncMock()
        from app.core.errors import SuperGETError

        with patch(
            "app.services.price_comparator.get_prices_for_product",
            new_callable=AsyncMock,
            side_effect=SuperGETError(message_en="API down"),
        ):
            result = await fetch_and_save_prices(db, product)

        assert result.matched is False
        assert len(result.prices) == 0
        assert result.product_name == product.name

    @pytest.mark.anyio
    async def test_no_prices_found(self) -> None:
        product = _mock_product()
        db = AsyncMock()

        with patch(
            "app.services.price_comparator.get_prices_for_product",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await fetch_and_save_prices(db, product)

        assert result.matched is False
        assert len(result.prices) == 0


# ---------------------------------------------------------------------------
# Async tests: fetch_prices_for_products (batch)
# ---------------------------------------------------------------------------


class TestFetchPricesForProducts:
    @pytest.mark.anyio
    async def test_fetches_multiple_products(self) -> None:
        pid1 = uuid.uuid4()
        pid2 = uuid.uuid4()
        product1 = _mock_product(product_id=pid1, name="חלב")
        product2 = _mock_product(product_id=pid2, name="לחם")

        db = AsyncMock()

        # DB returns products in order
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = product1
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = product2
        db.execute.side_effect = [mock_result1, mock_result2]

        with patch(
            "app.services.price_comparator.fetch_and_save_prices",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.side_effect = [
                ProductPriceResult(pid1, "חלב", [StorePrice("שופרסל", None, Decimal("6"), "חלב")], True),
                ProductPriceResult(pid2, "לחם", [], False),
            ]
            results = await fetch_prices_for_products(db, [pid1, pid2])

        assert len(results) == 2
        assert results[0].matched is True
        assert results[1].matched is False

    @pytest.mark.anyio
    async def test_skips_missing_products(self) -> None:
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        results = await fetch_prices_for_products(db, [uuid.uuid4()])
        assert len(results) == 0
