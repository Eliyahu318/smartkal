"""Tests for Claude AI receipt parser service."""

from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.receipt_parser import (
    ParsedItem,
    ParsedReceipt,
    _safe_decimal,
    _validate_and_build,
    parse_receipt,
)


# --- Unit tests for _safe_decimal ---


class TestSafeDecimal:
    def test_valid_number(self) -> None:
        assert _safe_decimal(12.90) == Decimal("12.9")

    def test_valid_string(self) -> None:
        assert _safe_decimal("99.50") == Decimal("99.50")

    def test_valid_int(self) -> None:
        assert _safe_decimal(5) == Decimal("5")

    def test_none_returns_none(self) -> None:
        assert _safe_decimal(None) is None

    def test_invalid_string(self) -> None:
        assert _safe_decimal("not-a-number") is None

    def test_empty_string(self) -> None:
        assert _safe_decimal("") is None


# --- Unit tests for _validate_and_build ---


class TestValidateAndBuild:
    def test_valid_receipt_data(self) -> None:
        data: dict[str, object] = {
            "store_name": "רמי לוי",
            "store_branch": "סניף מודיעין",
            "receipt_date": "2025-01-15",
            "total_amount": 234.50,
            "items": [
                {
                    "name": "חלב תנובה 3%",
                    "quantity": 2.0,
                    "unit_price": 6.90,
                    "total_price": 13.80,
                    "barcode": "7290000001234",
                },
                {
                    "name": "לחם אחיד",
                    "quantity": 1.0,
                    "unit_price": 7.50,
                    "total_price": 7.50,
                    "barcode": None,
                },
            ],
        }
        result = _validate_and_build(data)

        assert isinstance(result, ParsedReceipt)
        assert result.store_name == "רמי לוי"
        assert result.store_branch == "סניף מודיעין"
        assert result.receipt_date == "2025-01-15"
        assert result.total_amount == Decimal("234.5")
        assert len(result.items) == 2
        assert result.items[0].name == "חלב תנובה 3%"
        assert result.items[0].quantity == 2.0
        assert result.items[0].unit_price == Decimal("6.9")
        assert result.items[0].barcode == "7290000001234"
        assert result.items[1].barcode is None
        assert result.raw_json == data

    def test_missing_items_raises(self) -> None:
        from app.core.errors import ReceiptParsingError

        with pytest.raises(ReceiptParsingError, match="missing items"):
            _validate_and_build({"store_name": "test"})

    def test_items_not_list_raises(self) -> None:
        from app.core.errors import ReceiptParsingError

        with pytest.raises(ReceiptParsingError, match="missing items"):
            _validate_and_build({"items": "not a list"})

    def test_skips_invalid_items(self) -> None:
        data: dict[str, object] = {
            "store_name": None,
            "total_amount": None,
            "items": [
                {"name": ""},  # empty name
                {"quantity": 1},  # no name
                {"name": None},  # null name
                {"name": "  "},  # whitespace only name
                "not a dict",  # not a dict
                {"name": "מוצר תקין", "quantity": 1.0},  # valid
            ],
        }
        result = _validate_and_build(data)
        assert len(result.items) == 1
        assert result.items[0].name == "מוצר תקין"

    def test_defaults_quantity_to_1(self) -> None:
        data: dict[str, object] = {
            "items": [{"name": "ביצים", "unit_price": 15.0}],
        }
        result = _validate_and_build(data)
        assert result.items[0].quantity == 1.0

    def test_null_fields_handled(self) -> None:
        data: dict[str, object] = {
            "store_name": None,
            "store_branch": None,
            "receipt_date": None,
            "total_amount": None,
            "items": [{"name": "סבון"}],
        }
        result = _validate_and_build(data)
        assert result.store_name is None
        assert result.store_branch is None
        assert result.receipt_date is None
        assert result.total_amount is None


# --- Integration tests for parse_receipt ---


def _make_claude_response(content: str) -> SimpleNamespace:
    """Create a mock Claude API response."""
    block = SimpleNamespace(text=content)
    return SimpleNamespace(content=[block])


class TestParseReceiptValidJSON:
    @pytest.mark.anyio
    async def test_valid_receipt_parsed(self) -> None:
        receipt_json = json.dumps(
            {
                "store_name": "שופרסל",
                "store_branch": "דיל בראשון",
                "receipt_date": "2025-03-20",
                "total_amount": 187.40,
                "items": [
                    {
                        "name": "חלב תנובה 3% 1 ליטר",
                        "quantity": 2,
                        "unit_price": 6.90,
                        "total_price": 13.80,
                        "barcode": "7290000001234",
                    },
                    {
                        "name": "עגבניות שרי",
                        "quantity": 0.5,
                        "unit_price": 12.90,
                        "total_price": 6.45,
                        "barcode": None,
                    },
                ],
            },
            ensure_ascii=False,
        )
        mock_response = _make_claude_response(receipt_json)

        with (
            patch("app.services.receipt_parser.get_settings") as mock_settings,
            patch("app.services.receipt_parser.AsyncAnthropic") as mock_client_cls,
        ):
            mock_settings.return_value = MagicMock(anthropic_api_key="test-key")
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await parse_receipt("receipt text here")

        assert result.store_name == "שופרסל"
        assert result.store_branch == "דיל בראשון"
        assert result.receipt_date == "2025-03-20"
        assert result.total_amount == Decimal("187.4")
        assert len(result.items) == 2
        assert result.items[0].name == "חלב תנובה 3% 1 ליטר"
        assert result.items[0].quantity == 2.0
        assert result.items[0].barcode == "7290000001234"
        assert result.items[1].name == "עגבניות שרי"
        assert result.items[1].quantity == 0.5

    @pytest.mark.anyio
    async def test_json_with_markdown_fences(self) -> None:
        """Claude sometimes wraps JSON in ```json ... ``` blocks."""
        receipt_json = json.dumps(
            {
                "store_name": "רמי לוי",
                "items": [{"name": "לחם", "quantity": 1}],
            },
            ensure_ascii=False,
        )
        fenced = f"```json\n{receipt_json}\n```"
        mock_response = _make_claude_response(fenced)

        with (
            patch("app.services.receipt_parser.get_settings") as mock_settings,
            patch("app.services.receipt_parser.AsyncAnthropic") as mock_client_cls,
        ):
            mock_settings.return_value = MagicMock(anthropic_api_key="test-key")
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await parse_receipt("receipt text")

        assert result.store_name == "רמי לוי"
        assert len(result.items) == 1


class TestParseReceiptInvalidJSON:
    @pytest.mark.anyio
    async def test_invalid_json_all_retries_fail(self) -> None:
        """All attempts return invalid JSON — should raise ReceiptParsingError."""
        from app.core.errors import ReceiptParsingError

        mock_response = _make_claude_response("this is not json at all")

        with (
            patch("app.services.receipt_parser.get_settings") as mock_settings,
            patch("app.services.receipt_parser.AsyncAnthropic") as mock_client_cls,
        ):
            mock_settings.return_value = MagicMock(anthropic_api_key="test-key")
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ReceiptParsingError, match="Failed to parse"):
                await parse_receipt("some receipt text")

        # Should have been called 3 times (1 + 2 retries)
        assert mock_client.messages.create.call_count == 3

    @pytest.mark.anyio
    async def test_invalid_json_then_valid_on_retry(self) -> None:
        """First attempt returns invalid JSON, retry succeeds."""
        valid_json = json.dumps(
            {
                "store_name": "יוחננוף",
                "items": [{"name": "אורז", "quantity": 1}],
            },
            ensure_ascii=False,
        )
        invalid_response = _make_claude_response("not json")
        valid_response = _make_claude_response(valid_json)

        with (
            patch("app.services.receipt_parser.get_settings") as mock_settings,
            patch("app.services.receipt_parser.AsyncAnthropic") as mock_client_cls,
        ):
            mock_settings.return_value = MagicMock(anthropic_api_key="test-key")
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                side_effect=[invalid_response, valid_response]
            )
            mock_client_cls.return_value = mock_client

            result = await parse_receipt("receipt text")

        assert result.store_name == "יוחננוף"
        assert mock_client.messages.create.call_count == 2


class TestParseReceiptEmptyReceipt:
    @pytest.mark.anyio
    async def test_empty_text_raises(self) -> None:
        from app.core.errors import ReceiptParsingError

        with pytest.raises(ReceiptParsingError, match="empty"):
            await parse_receipt("")

    @pytest.mark.anyio
    async def test_whitespace_only_raises(self) -> None:
        from app.core.errors import ReceiptParsingError

        with pytest.raises(ReceiptParsingError, match="empty"):
            await parse_receipt("   \n\t  ")


class TestParseReceiptAPIErrors:
    @pytest.mark.anyio
    async def test_no_api_key_raises(self) -> None:
        from app.core.errors import ClaudeAPIError

        with patch("app.services.receipt_parser.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(anthropic_api_key="")

            with pytest.raises(ClaudeAPIError, match="not configured"):
                await parse_receipt("receipt text")

    @pytest.mark.anyio
    async def test_api_failure_retries_and_raises(self) -> None:
        from app.core.errors import ClaudeAPIError

        with (
            patch("app.services.receipt_parser.get_settings") as mock_settings,
            patch("app.services.receipt_parser.AsyncAnthropic") as mock_client_cls,
        ):
            mock_settings.return_value = MagicMock(anthropic_api_key="test-key")
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                side_effect=RuntimeError("API timeout")
            )
            mock_client_cls.return_value = mock_client

            with pytest.raises(ClaudeAPIError, match="failed after"):
                await parse_receipt("receipt text")

        assert mock_client.messages.create.call_count == 3

    @pytest.mark.anyio
    async def test_api_error_then_success_on_retry(self) -> None:
        valid_json = json.dumps(
            {
                "store_name": "מגה",
                "items": [{"name": "קפה", "quantity": 1}],
            },
            ensure_ascii=False,
        )
        valid_response = _make_claude_response(valid_json)

        with (
            patch("app.services.receipt_parser.get_settings") as mock_settings,
            patch("app.services.receipt_parser.AsyncAnthropic") as mock_client_cls,
        ):
            mock_settings.return_value = MagicMock(anthropic_api_key="test-key")
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                side_effect=[RuntimeError("timeout"), valid_response]
            )
            mock_client_cls.return_value = mock_client

            result = await parse_receipt("receipt text")

        assert result.store_name == "מגה"
        assert mock_client.messages.create.call_count == 2


class TestParseReceiptPromptContent:
    @pytest.mark.anyio
    async def test_receipt_text_included_in_prompt(self) -> None:
        """Verify that the receipt text is sent to Claude in the prompt."""
        valid_json = json.dumps(
            {"store_name": "test", "items": [{"name": "x", "quantity": 1}]},
        )
        mock_response = _make_claude_response(valid_json)
        receipt_text = "הקבלה שלי עם מוצרים"

        with (
            patch("app.services.receipt_parser.get_settings") as mock_settings,
            patch("app.services.receipt_parser.AsyncAnthropic") as mock_client_cls,
        ):
            mock_settings.return_value = MagicMock(anthropic_api_key="test-key")
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            await parse_receipt(receipt_text)

        call_args = mock_client.messages.create.call_args
        messages = call_args.kwargs["messages"]
        assert receipt_text in messages[0]["content"]


class TestParsedDataclasses:
    def test_parsed_item_creation(self) -> None:
        item = ParsedItem(
            name="חלב",
            quantity=1.0,
            unit_price=Decimal("6.90"),
            total_price=Decimal("6.90"),
            barcode=None,
        )
        assert item.name == "חלב"
        assert item.quantity == 1.0

    def test_parsed_receipt_defaults(self) -> None:
        receipt = ParsedReceipt(
            store_name=None,
            store_branch=None,
            receipt_date=None,
            total_amount=None,
        )
        assert receipt.items == []
        assert receipt.raw_json == {}
