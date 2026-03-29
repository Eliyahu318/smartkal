"""Tests for US-019: Receipt API endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.receipt_parser import ParsedItem, ParsedReceipt


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

FAKE_USER_ID = uuid.uuid4()
FAKE_RECEIPT_ID = uuid.uuid4()
FAKE_PURCHASE_ID = uuid.uuid4()


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


def _mock_receipt(
    receipt_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    store_name: str = "רמי לוי",
    status: str = "parsed",
) -> MagicMock:
    now = datetime.now(timezone.utc)
    receipt = MagicMock()
    receipt.id = receipt_id or FAKE_RECEIPT_ID
    receipt.user_id = user_id or FAKE_USER_ID
    receipt.store_name = store_name
    receipt.store_branch = "סניף תל אביב"
    receipt.receipt_date = date(2025, 1, 15)
    receipt.total_amount = Decimal("156.90")
    receipt.raw_text = "receipt text"
    receipt.parsed_json = {"store_name": store_name, "items": []}
    receipt.pdf_filename = "receipt.pdf"
    receipt.status = status
    receipt.created_at = now
    receipt.updated_at = now
    receipt.purchases = []
    return receipt


def _mock_purchase(
    purchase_id: uuid.UUID | None = None,
    receipt_id: uuid.UUID | None = None,
    raw_name: str = "חלב תנובה 3%",
) -> MagicMock:
    now = datetime.now(timezone.utc)
    purchase = MagicMock()
    purchase.id = purchase_id or FAKE_PURCHASE_ID
    purchase.receipt_id = receipt_id or FAKE_RECEIPT_ID
    purchase.product_id = None
    purchase.raw_name = raw_name
    purchase.quantity = 1.0
    purchase.unit_price = Decimal("6.90")
    purchase.total_price = Decimal("6.90")
    purchase.barcode = "7290000123456"
    purchase.matched = False
    purchase.created_at = now
    purchase.updated_at = now
    return purchase


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


def _make_parsed_receipt() -> ParsedReceipt:
    """Create a sample ParsedReceipt for mocking."""
    return ParsedReceipt(
        store_name="רמי לוי",
        store_branch="סניף תל אביב",
        receipt_date="2025-01-15",
        total_amount=Decimal("156.90"),
        items=[
            ParsedItem(
                name="חלב תנובה 3%",
                quantity=2.0,
                unit_price=Decimal("6.90"),
                total_price=Decimal("13.80"),
                barcode="7290000123456",
            ),
            ParsedItem(
                name="לחם אחיד",
                quantity=1.0,
                unit_price=Decimal("5.50"),
                total_price=Decimal("5.50"),
                barcode=None,
            ),
        ],
        raw_json={
            "store_name": "רמי לוי",
            "store_branch": "סניף תל אביב",
            "receipt_date": "2025-01-15",
            "total_amount": 156.90,
            "items": [],
        },
    )


def _valid_pdf_bytes() -> bytes:
    """Return minimal bytes that start with %PDF magic."""
    return b"%PDF-1.4 fake content for testing"


# ---------------------------------------------------------------------------
# POST /api/v1/receipts/upload — file validation
# ---------------------------------------------------------------------------


class TestUploadValidation:
    """Test file validation in the upload endpoint."""

    @pytest.mark.anyio
    async def test_rejects_non_pdf(self) -> None:
        """Non-PDF file should be rejected with 422."""
        mock_session = AsyncMock(spec=AsyncSession)
        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/receipts/upload",
                headers={"Authorization": "Bearer fake"},
                files={"file": ("image.png", b"\x89PNG\r\n\x1a\n fake", "image/png")},
            )

        assert response.status_code == 422
        assert "PDF" in response.json()["error"]["message_en"]

    @pytest.mark.anyio
    async def test_rejects_oversized_file(self) -> None:
        """File over 10MB should be rejected."""
        mock_session = AsyncMock(spec=AsyncSession)
        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        # 10MB + 1 byte, starting with PDF magic
        oversized = b"%PDF" + b"\x00" * (10 * 1024 * 1024 + 1)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/receipts/upload",
                headers={"Authorization": "Bearer fake"},
                files={"file": ("big.pdf", oversized, "application/pdf")},
            )

        assert response.status_code == 422
        assert "10MB" in response.json()["error"]["message_en"]


# ---------------------------------------------------------------------------
# POST /api/v1/receipts/upload — successful upload flow (mocked)
# ---------------------------------------------------------------------------


class TestUploadFlow:
    """Test the full upload flow with mocked PDF extraction and Claude parsing."""

    @pytest.mark.anyio
    @patch("app.api.v1.receipt.match_receipt_purchases")
    @patch("app.api.v1.receipt.parse_receipt")
    @patch("app.api.v1.receipt.extract_text_from_pdf")
    async def test_upload_success(
        self,
        mock_extract: AsyncMock,
        mock_parse: AsyncMock,
        mock_match: AsyncMock,
    ) -> None:
        """Successful upload creates receipt and purchase records."""
        mock_extract.return_value = "receipt text content"
        mock_parse.return_value = _make_parsed_receipt()
        mock_match.return_value = {
            "barcode": 1, "exact_name": 0, "fuzzy": 0, "new": 1, "completed_items": 0,
        }

        mock_session = AsyncMock(spec=AsyncSession)

        # Track objects added to the session
        added_objects: list[Any] = []
        original_add = mock_session.add

        def track_add(obj: Any) -> None:
            # Assign fake IDs and timestamps for response serialization
            if not hasattr(obj, '_tracked'):
                obj._tracked = True
                if hasattr(obj, 'id') and obj.id is None:
                    obj.id = uuid.uuid4()
                now = datetime.now(timezone.utc)
                if hasattr(obj, 'created_at'):
                    obj.created_at = now
                if hasattr(obj, 'updated_at'):
                    obj.updated_at = now
            added_objects.append(obj)

        mock_session.add.side_effect = track_add

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/receipts/upload",
                headers={"Authorization": "Bearer fake"},
                files={"file": ("receipt.pdf", _valid_pdf_bytes(), "application/pdf")},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["parsed_item_count"] == 2
        assert data["receipt"]["store_name"] == "רמי לוי"
        assert data["receipt"]["status"] == "parsed"
        assert len(data["receipt"]["purchases"]) == 2
        assert data["receipt"]["purchases"][0]["raw_name"] == "חלב תנובה 3%"
        assert data["receipt"]["purchases"][1]["raw_name"] == "לחם אחיד"
        assert data["match_counts"]["barcode"] == 1
        assert data["match_counts"]["new"] == 1

        # Verify PDF extraction and Claude parse were called
        mock_extract.assert_called_once()
        mock_parse.assert_called_once_with("receipt text content")
        mock_match.assert_called_once()

    @pytest.mark.anyio
    @patch("app.api.v1.receipt.match_receipt_purchases")
    @patch("app.api.v1.receipt.parse_receipt")
    @patch("app.api.v1.receipt.extract_text_from_pdf")
    async def test_upload_with_invalid_date(
        self,
        mock_extract: AsyncMock,
        mock_parse: AsyncMock,
        mock_match: AsyncMock,
    ) -> None:
        """Upload handles invalid receipt_date gracefully."""
        parsed = _make_parsed_receipt()
        parsed.receipt_date = "not-a-date"
        mock_extract.return_value = "text"
        mock_parse.return_value = parsed
        mock_match.return_value = {
            "barcode": 0, "exact_name": 0, "fuzzy": 0, "new": 2, "completed_items": 0,
        }

        mock_session = AsyncMock(spec=AsyncSession)

        def track_add(obj: Any) -> None:
            if not hasattr(obj, '_tracked'):
                obj._tracked = True
                if hasattr(obj, 'id') and obj.id is None:
                    obj.id = uuid.uuid4()
                now = datetime.now(timezone.utc)
                if hasattr(obj, 'created_at'):
                    obj.created_at = now
                if hasattr(obj, 'updated_at'):
                    obj.updated_at = now

        mock_session.add.side_effect = track_add

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/receipts/upload",
                headers={"Authorization": "Bearer fake"},
                files={"file": ("receipt.pdf", _valid_pdf_bytes(), "application/pdf")},
            )

        assert response.status_code == 201
        assert response.json()["receipt"]["receipt_date"] is None


# ---------------------------------------------------------------------------
# GET /api/v1/receipts/{id} — retrieve single receipt
# ---------------------------------------------------------------------------


class TestGetReceipt:
    """Test retrieving a single receipt with purchases."""

    @pytest.mark.anyio
    async def test_get_receipt_success(self) -> None:
        """Found receipt returns 200 with purchases."""
        mock_session = AsyncMock(spec=AsyncSession)

        receipt = _mock_receipt()
        purchase = _mock_purchase(receipt_id=receipt.id)
        receipt.purchases = [purchase]

        result = MagicMock()
        result.scalar_one_or_none.return_value = receipt
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/receipts/{receipt.id}",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["store_name"] == "רמי לוי"
        assert len(data["purchases"]) == 1
        assert data["purchases"][0]["raw_name"] == "חלב תנובה 3%"

    @pytest.mark.anyio
    async def test_get_receipt_not_found(self) -> None:
        """Missing receipt returns 404."""
        mock_session = AsyncMock(spec=AsyncSession)

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/receipts/{uuid.uuid4()}",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_get_receipt_user_isolation(self) -> None:
        """Receipt belonging to another user returns 404."""
        mock_session = AsyncMock(spec=AsyncSession)

        # The DB query filters by user_id, so a receipt for another user won't match
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        other_receipt_id = uuid.uuid4()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/receipts/{other_receipt_id}",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/receipts — paginated list
# ---------------------------------------------------------------------------


class TestListReceipts:
    """Test paginated receipt listing."""

    @pytest.mark.anyio
    async def test_list_receipts_empty(self) -> None:
        """Empty list returns zero total and empty array."""
        mock_session = AsyncMock(spec=AsyncSession)

        # First call: count query
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0

        # Second call: receipts query
        receipts_result = MagicMock()
        receipts_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [count_result, receipts_result]

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/receipts",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["receipts"] == []
        assert data["page"] == 1

    @pytest.mark.anyio
    async def test_list_receipts_with_data(self) -> None:
        """List returns receipts with pagination info."""
        mock_session = AsyncMock(spec=AsyncSession)

        r1 = _mock_receipt(receipt_id=uuid.uuid4(), store_name="רמי לוי")
        r2 = _mock_receipt(receipt_id=uuid.uuid4(), store_name="שופרסל")

        count_result = MagicMock()
        count_result.scalar_one.return_value = 2

        receipts_result = MagicMock()
        receipts_result.scalars.return_value.all.return_value = [r1, r2]

        mock_session.execute.side_effect = [count_result, receipts_result]

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/receipts?page=1&page_size=10",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["receipts"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 10

    @pytest.mark.anyio
    async def test_list_receipts_pagination(self) -> None:
        """Pagination parameters are respected."""
        mock_session = AsyncMock(spec=AsyncSession)

        count_result = MagicMock()
        count_result.scalar_one.return_value = 25

        receipts_result = MagicMock()
        receipts_result.scalars.return_value.all.return_value = [
            _mock_receipt(receipt_id=uuid.uuid4()) for _ in range(5)
        ]

        mock_session.execute.side_effect = [count_result, receipts_result]

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/receipts?page=3&page_size=5",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 25
        assert data["page"] == 3
        assert data["page_size"] == 5


# ---------------------------------------------------------------------------
# Auth protection — all endpoints require authentication
# ---------------------------------------------------------------------------


class TestReceiptAuthProtection:
    """All receipt endpoints require authentication."""

    @pytest.mark.anyio
    async def test_upload_requires_auth(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/receipts/upload",
                files={"file": ("r.pdf", b"%PDF-fake", "application/pdf")},
            )
        assert response.status_code in (401, 403)

    @pytest.mark.anyio
    async def test_get_receipt_requires_auth(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/receipts/{uuid.uuid4()}")
        assert response.status_code in (401, 403)

    @pytest.mark.anyio
    async def test_list_receipts_requires_auth(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/receipts")
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Unit tests for _validate_pdf helper
# ---------------------------------------------------------------------------


class TestValidatePdf:
    """Test the PDF validation helper."""

    def test_valid_pdf_passes(self) -> None:
        from app.api.v1.receipt import _validate_pdf

        # Should not raise
        _validate_pdf(b"%PDF-1.4 content", "test.pdf")

    def test_non_pdf_raises(self) -> None:
        from app.api.v1.receipt import _validate_pdf
        from app.core.errors import ValidationError

        with pytest.raises(ValidationError, match="PDF"):
            _validate_pdf(b"not a pdf", "test.txt")

    def test_oversized_raises(self) -> None:
        from app.api.v1.receipt import _validate_pdf
        from app.core.errors import ValidationError

        oversized = b"%PDF" + b"\x00" * (10 * 1024 * 1024 + 1)
        with pytest.raises(ValidationError, match="10MB"):
            _validate_pdf(oversized, "big.pdf")

    def test_empty_file_raises(self) -> None:
        from app.api.v1.receipt import _validate_pdf
        from app.core.errors import ValidationError

        with pytest.raises(ValidationError):
            _validate_pdf(b"", "empty.pdf")


# ---------------------------------------------------------------------------
# Unit tests for _build_purchases_from_parsed helper
# ---------------------------------------------------------------------------


class TestBuildPurchases:
    """Test building Purchase objects from parsed receipt data."""

    def test_builds_correct_count(self) -> None:
        from app.api.v1.receipt import _build_purchases_from_parsed

        parsed = _make_parsed_receipt()
        receipt_id = uuid.uuid4()
        purchases = _build_purchases_from_parsed(receipt_id, parsed)

        assert len(purchases) == 2
        assert purchases[0].raw_name == "חלב תנובה 3%"
        assert purchases[0].quantity == 2.0
        assert purchases[0].unit_price == Decimal("6.90")
        assert purchases[0].total_price == Decimal("13.80")
        assert purchases[0].barcode == "7290000123456"
        assert purchases[0].receipt_id == receipt_id
        assert purchases[0].matched is False

        assert purchases[1].raw_name == "לחם אחיד"
        assert purchases[1].barcode is None

    def test_empty_items(self) -> None:
        from app.api.v1.receipt import _build_purchases_from_parsed

        parsed = ParsedReceipt(
            store_name="test",
            store_branch=None,
            receipt_date=None,
            total_amount=None,
            items=[],
        )
        purchases = _build_purchases_from_parsed(uuid.uuid4(), parsed)
        assert len(purchases) == 0
