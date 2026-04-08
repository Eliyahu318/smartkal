"""Tests for US-020: Product matching from receipts."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.product_matcher import (
    FUZZY_THRESHOLD,
    match_purchase_to_product,
    match_receipt_purchases,
    normalize_hebrew_name,
)


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

FAKE_USER_ID = uuid.uuid4()
FAKE_PRODUCT_ID = uuid.uuid4()
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


def _mock_product(
    product_id: uuid.UUID | None = None,
    name: str = "חלב תנובה 3%",
    normalized_name: str | None = None,
    barcode: str | None = None,
) -> MagicMock:
    product = MagicMock()
    product.id = product_id or FAKE_PRODUCT_ID
    product.name = name
    product.normalized_name = normalized_name or normalize_hebrew_name(name)
    product.barcode = barcode
    product.category_id = None
    return product


def _mock_purchase(
    raw_name: str = "חלב תנובה 3%",
    barcode: str | None = None,
    quantity: float = 1.0,
    unit_price: Decimal | None = Decimal("6.90"),
    total_price: Decimal | None = Decimal("6.90"),
) -> MagicMock:
    purchase = MagicMock()
    purchase.raw_name = raw_name
    purchase.barcode = barcode
    purchase.quantity = quantity
    purchase.unit_price = unit_price
    purchase.total_price = total_price
    purchase.product_id = None
    purchase.matched = False
    purchase.receipt_id = uuid.uuid4()
    return purchase


def _mock_list_item(
    item_id: uuid.UUID | None = None,
    name: str = "חלב",
    status: str = "active",
    product_id: uuid.UUID | None = None,
) -> MagicMock:
    item = MagicMock()
    item.id = item_id or FAKE_ITEM_ID
    item.user_id = FAKE_USER_ID
    item.name = name
    item.status = status
    item.product_id = product_id
    item.category_id = None
    item.quantity = None
    item.note = None
    item.source = "manual"
    item.confidence = None
    item.display_order = 0
    item.auto_refresh_days = None
    item.system_refresh_days = None
    item.next_refresh_at = None
    item.last_completed_at = None
    item.last_activated_at = None
    item.created_at = datetime.now(timezone.utc)
    item.updated_at = datetime.now(timezone.utc)
    return item


# ---------------------------------------------------------------------------
# Unit tests for normalize_hebrew_name
# ---------------------------------------------------------------------------


class TestNormalizeHebrewName:
    """Test Hebrew name normalization."""

    def test_basic_hebrew(self) -> None:
        assert normalize_hebrew_name("חלב תנובה 3%") == "חלב תנובה 3%"

    def test_strips_punctuation(self) -> None:
        assert normalize_hebrew_name('חלב (תנובה) "3%"') == "חלב תנובה 3%"

    def test_collapses_whitespace(self) -> None:
        assert normalize_hebrew_name("חלב   תנובה    3%") == "חלב תנובה 3%"

    def test_lowercase_latin(self) -> None:
        result = normalize_hebrew_name("Tnuva חלב")
        assert result == "tnuva חלב"

    def test_empty_string(self) -> None:
        assert normalize_hebrew_name("") == ""

    def test_preserves_digits(self) -> None:
        assert normalize_hebrew_name("1 ליטר") == "1 ליטר"


# ---------------------------------------------------------------------------
# Unit tests for match_purchase_to_product — barcode match
# ---------------------------------------------------------------------------


class TestBarcodeMatch:
    """Test barcode exact matching."""

    @pytest.mark.anyio
    async def test_barcode_match_found(self) -> None:
        """Purchase with barcode matches existing product by barcode."""
        db = AsyncMock(spec=AsyncSession)
        product = _mock_product(barcode="7290000123456")

        # Barcode query returns the product
        result = MagicMock()
        result.scalar_one_or_none.return_value = product
        db.execute.return_value = result

        purchase = _mock_purchase(
            raw_name="חלב תנובה 3% 1 ליטר",
            barcode="7290000123456",
        )

        matched_product, match_type = await match_purchase_to_product(db, purchase)

        assert match_type == "barcode"
        assert matched_product.id == product.id

    @pytest.mark.anyio
    async def test_barcode_no_match_falls_through(self) -> None:
        """Purchase with unmatched barcode falls through to name matching."""
        db = AsyncMock(spec=AsyncSession)

        # Barcode query: no match
        barcode_result = MagicMock()
        barcode_result.scalar_one_or_none.return_value = None

        # Name query: no match
        name_result = MagicMock()
        name_result.scalar_one_or_none.return_value = None

        # Fuzzy query: no products
        fuzzy_result = MagicMock()
        fuzzy_result.scalars.return_value.all.return_value = []

        db.execute.side_effect = [barcode_result, name_result, fuzzy_result]

        purchase = _mock_purchase(
            raw_name="מוצר חדש",
            barcode="9999999999999",
        )

        matched_product, match_type = await match_purchase_to_product(db, purchase)

        assert match_type == "new"


# ---------------------------------------------------------------------------
# Unit tests for match_purchase_to_product — exact name match
# ---------------------------------------------------------------------------


class TestExactNameMatch:
    """Test normalized name exact matching."""

    @pytest.mark.anyio
    async def test_exact_name_match(self) -> None:
        """Purchase matches by exact normalized name."""
        db = AsyncMock(spec=AsyncSession)
        product = _mock_product(name="חלב תנובה 3%")

        # Name query returns the product
        result = MagicMock()
        result.scalar_one_or_none.return_value = product
        db.execute.return_value = result

        purchase = _mock_purchase(raw_name="חלב תנובה 3%", barcode=None)

        matched_product, match_type = await match_purchase_to_product(db, purchase)

        assert match_type == "exact_name"
        assert matched_product.id == product.id


# ---------------------------------------------------------------------------
# Unit tests for match_purchase_to_product — fuzzy match
# ---------------------------------------------------------------------------


class TestFuzzyMatch:
    """Test fuzzy Hebrew matching."""

    @pytest.mark.anyio
    async def test_fuzzy_match_above_threshold(self) -> None:
        """Similar Hebrew names match above threshold."""
        db = AsyncMock(spec=AsyncSession)

        # Existing product
        product = _mock_product(name="חלב תנובה 3% 1 ליטר")

        # No exact name match
        name_result = MagicMock()
        name_result.scalar_one_or_none.return_value = None

        # Fuzzy: return the product
        fuzzy_result = MagicMock()
        fuzzy_result.scalars.return_value.all.return_value = [product]

        db.execute.side_effect = [name_result, fuzzy_result]

        # Slightly different name
        purchase = _mock_purchase(raw_name="חלב תנובה 3% ליטר 1", barcode=None)

        matched_product, match_type = await match_purchase_to_product(db, purchase)

        assert match_type == "fuzzy"
        assert matched_product.id == product.id

    @pytest.mark.anyio
    async def test_fuzzy_match_below_threshold(self) -> None:
        """Dissimilar names don't match — creates new product."""
        db = AsyncMock(spec=AsyncSession)

        # Existing product with very different name
        product = _mock_product(name="נייר טואלט")

        # No exact match
        name_result = MagicMock()
        name_result.scalar_one_or_none.return_value = None

        # Fuzzy: return the product (but score will be below threshold)
        fuzzy_result = MagicMock()
        fuzzy_result.scalars.return_value.all.return_value = [product]

        db.execute.side_effect = [name_result, fuzzy_result]

        purchase = _mock_purchase(raw_name="חלב תנובה 3%", barcode=None)

        matched_product, match_type = await match_purchase_to_product(db, purchase)

        assert match_type == "new"


# ---------------------------------------------------------------------------
# Unit tests for match_purchase_to_product — create new product
# ---------------------------------------------------------------------------


class TestNewProduct:
    """Test new product creation when no match found."""

    @pytest.mark.anyio
    async def test_creates_new_product(self) -> None:
        """When nothing matches, a new product is created."""
        db = AsyncMock(spec=AsyncSession)

        # No matches at any stage
        name_result = MagicMock()
        name_result.scalar_one_or_none.return_value = None

        fuzzy_result = MagicMock()
        fuzzy_result.scalars.return_value.all.return_value = []

        db.execute.side_effect = [name_result, fuzzy_result]

        # Track db.add calls
        added: list[Any] = []

        def track_add(obj: Any) -> None:
            if hasattr(obj, "name"):
                obj.id = uuid.uuid4()
            added.append(obj)

        db.add.side_effect = track_add

        purchase = _mock_purchase(raw_name="מוצר חדש לגמרי", barcode=None)

        matched_product, match_type = await match_purchase_to_product(db, purchase)

        assert match_type == "new"
        assert matched_product.name == "מוצר חדש לגמרי"
        assert matched_product.normalized_name == normalize_hebrew_name("מוצר חדש לגמרי")
        assert len(added) == 1  # One Product added


# ---------------------------------------------------------------------------
# Test upgrade endpoint
# ---------------------------------------------------------------------------


class TestUpgradeEndpoint:
    """Test POST /api/v1/list/items/{id}/upgrade endpoint."""

    @pytest.mark.anyio
    async def test_upgrade_item_name(self) -> None:
        """Upgrade changes the item name and linked product name."""
        mock_session = AsyncMock(spec=AsyncSession)

        item = _mock_list_item(name="חלב", product_id=FAKE_PRODUCT_ID)
        product = _mock_product(product_id=FAKE_PRODUCT_ID, name="חלב")

        # First execute: get_user_item
        item_result = MagicMock()
        item_result.scalar_one_or_none.return_value = item

        # Second execute: get product
        product_result = MagicMock()
        product_result.scalar_one_or_none.return_value = product

        mock_session.execute.side_effect = [item_result, product_result]

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/list/items/{item.id}/upgrade",
                headers={"Authorization": "Bearer fake"},
                json={"precise_name": "חלב תנובה 3% 1 ליטר"},
            )

        assert response.status_code == 200
        assert item.name == "חלב תנובה 3% 1 ליטר"
        assert product.name == "חלב תנובה 3% 1 ליטר"

    @pytest.mark.anyio
    async def test_upgrade_item_without_product(self) -> None:
        """Upgrade works even when item has no linked product."""
        mock_session = AsyncMock(spec=AsyncSession)

        item = _mock_list_item(name="חלב", product_id=None)

        item_result = MagicMock()
        item_result.scalar_one_or_none.return_value = item

        mock_session.execute.side_effect = [item_result]

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/list/items/{item.id}/upgrade",
                headers={"Authorization": "Bearer fake"},
                json={"precise_name": "חלב תנובה 3% 1 ליטר"},
            )

        assert response.status_code == 200
        assert item.name == "חלב תנובה 3% 1 ליטר"

    @pytest.mark.anyio
    async def test_upgrade_not_found(self) -> None:
        """Upgrade returns 404 for missing item."""
        mock_session = AsyncMock(spec=AsyncSession)

        item_result = MagicMock()
        item_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = item_result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/list/items/{uuid.uuid4()}/upgrade",
                headers={"Authorization": "Bearer fake"},
                json={"precise_name": "חלב תנובה 3% 1 ליטר"},
            )

        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_upgrade_requires_auth(self) -> None:
        """Upgrade endpoint requires authentication."""
        app = _make_test_app()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/list/items/{uuid.uuid4()}/upgrade",
                json={"precise_name": "test"},
            )
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Integration-style tests for match_receipt_purchases
# ---------------------------------------------------------------------------


class TestMatchReceiptPurchases:
    """Test the full receipt matching flow."""

    @pytest.mark.anyio
    @patch("app.services.product_matcher.calculate_refresh_for_item")
    async def test_matches_and_completes_list_items(
        self, mock_refresh: AsyncMock
    ) -> None:
        """Matching a purchase completes corresponding list items."""
        mock_refresh.return_value = (7, 0.4, None)

        db = AsyncMock(spec=AsyncSession)

        # Create a receipt with one purchase
        receipt = MagicMock()
        receipt.id = uuid.uuid4()
        purchase = _mock_purchase(raw_name="חלב תנובה 3%", barcode="7290000123456")
        receipt.purchases = [purchase]

        # Product found by barcode
        product = _mock_product(name="חלב תנובה 3%", barcode="7290000123456")
        barcode_result = MagicMock()
        barcode_result.scalar_one_or_none.return_value = product

        # No active list items matching by product_id
        items_by_product_result = MagicMock()
        items_by_product_result.scalars.return_value.all.return_value = []

        # No unlinked list items either
        items_unlinked_result = MagicMock()
        items_unlinked_result.scalars.return_value.all.return_value = []

        # No existing completed item for this product
        existing_completed_result = MagicMock()
        existing_completed_result.scalar_one_or_none.return_value = None

        # Default category lookup returns None
        default_category_result = MagicMock()
        default_category_result.scalar_one_or_none.return_value = None

        db.execute.side_effect = [
            barcode_result,
            items_by_product_result,
            items_unlinked_result,
            existing_completed_result,
            default_category_result,
        ]

        counts = await match_receipt_purchases(
            db, receipt, FAKE_USER_ID, purchases=[purchase],
        )

        assert counts["barcode"] == 1
        assert purchase.product_id == product.id
        assert purchase.matched is True

    @pytest.mark.anyio
    @patch("app.services.product_matcher.calculate_refresh_for_item")
    async def test_completes_matching_list_item(
        self, mock_refresh: AsyncMock
    ) -> None:
        """When a matching list item exists, it's marked as completed.

        New flow (post-dedup refactor):
          1. barcode lookup -> product
          2. _alias_target -> None
          3. _direct_target (active) -> list_item
        """
        mock_refresh.return_value = (14, 0.3, None)

        db = AsyncMock(spec=AsyncSession)

        product = _mock_product(name="חלב תנובה 3%", barcode="7290000123456")

        # Active list item linked to same product
        list_item = _mock_list_item(
            name="חלב תנובה 3%",
            status="active",
            product_id=product.id,
        )
        list_item.canonical_key = None

        receipt = MagicMock()
        receipt.id = uuid.uuid4()
        purchase = _mock_purchase(raw_name="חלב תנובה 3%", barcode="7290000123456")
        receipt.purchases = [purchase]

        # 1. Barcode lookup
        barcode_result = MagicMock()
        barcode_result.scalar_one_or_none.return_value = product

        # 2. _alias_target — no explicit alias for this product
        alias_result = MagicMock()
        alias_result.scalar_one_or_none.return_value = None

        # 3. _direct_target — finds the active list_item via product_id
        direct_active_result = MagicMock()
        direct_active_result.scalar_one_or_none.return_value = list_item

        db.execute.side_effect = [
            barcode_result,
            alias_result,
            direct_active_result,
        ]

        counts = await match_receipt_purchases(
            db, receipt, FAKE_USER_ID, purchases=[purchase],
        )

        assert counts["completed_items"] == 1
        assert counts["completed_via_alias"] == 0  # found via direct, not alias
        assert counts["auto_merged_to_existing"] == 0
        assert list_item.status == "completed"
        assert list_item.last_completed_at is not None
        assert list_item.source == "receipt"


# ---------------------------------------------------------------------------
# resolve_list_item_target — the per-user dedup priority chain
# ---------------------------------------------------------------------------


class TestResolveListItemTarget:
    """Verify each branch of the resolve_list_item_target priority chain.

    Order: alias → direct_active → direct_any → canonical → fuzzy_unlinked → none.
    Each branch's mock sequence is wired to return the expected target at the
    expected step.
    """

    @pytest.mark.anyio
    async def test_alias_path(self) -> None:
        """When an explicit alias exists, it wins over everything else."""
        from app.services.product_matcher import resolve_list_item_target

        db = AsyncMock(spec=AsyncSession)
        product = _mock_product()
        target = _mock_list_item(name="עגבניות שרי")

        alias_result = MagicMock()
        alias_result.scalar_one_or_none.return_value = target
        db.execute.return_value = alias_result

        item, source = await resolve_list_item_target(
            db, FAKE_USER_ID, product, "עגבניות שרי"
        )

        assert source == "alias"
        assert item is target

    @pytest.mark.anyio
    async def test_direct_active_path(self) -> None:
        """No alias → falls through to direct active product link."""
        from app.services.product_matcher import resolve_list_item_target

        db = AsyncMock(spec=AsyncSession)
        product = _mock_product()
        target = _mock_list_item(name="חלב 3%", product_id=product.id)

        # 1. alias → None
        alias_result = MagicMock()
        alias_result.scalar_one_or_none.return_value = None
        # 2. direct active → target
        direct_active_result = MagicMock()
        direct_active_result.scalar_one_or_none.return_value = target

        db.execute.side_effect = [alias_result, direct_active_result]

        item, source = await resolve_list_item_target(
            db, FAKE_USER_ID, product, "חלב 3%"
        )

        assert source == "direct"
        assert item is target

    @pytest.mark.anyio
    async def test_canonical_path(self) -> None:
        """No alias, no direct → falls through to canonical_key match."""
        from app.services.product_matcher import resolve_list_item_target

        db = AsyncMock(spec=AsyncSession)
        product = _mock_product()
        target = _mock_list_item(name="עגבניות שרי")
        target.canonical_key = "עגבניות שרי"

        alias_result = MagicMock()
        alias_result.scalar_one_or_none.return_value = None
        direct_active_result = MagicMock()
        direct_active_result.scalar_one_or_none.return_value = None
        direct_any_result = MagicMock()
        direct_any_result.scalar_one_or_none.return_value = None
        canonical_result = MagicMock()
        canonical_result.scalar_one_or_none.return_value = target

        db.execute.side_effect = [
            alias_result,
            direct_active_result,
            direct_any_result,
            canonical_result,
        ]

        item, source = await resolve_list_item_target(
            db, FAKE_USER_ID, product, "עגבניות שרי"
        )

        assert source == "canonical"
        assert item is target

    @pytest.mark.anyio
    async def test_no_match_returns_none(self) -> None:
        """All paths exhausted → (None, 'none')."""
        from app.services.product_matcher import resolve_list_item_target

        db = AsyncMock(spec=AsyncSession)
        product = _mock_product()

        # All four queries return None / empty
        empty_one = MagicMock()
        empty_one.scalar_one_or_none.return_value = None
        empty_list = MagicMock()
        empty_list.scalars.return_value.all.return_value = []

        db.execute.side_effect = [
            empty_one,  # alias
            empty_one,  # direct active
            empty_one,  # direct any
            empty_one,  # canonical
            empty_list,  # fuzzy_unlinked
        ]

        item, source = await resolve_list_item_target(
            db, FAKE_USER_ID, product, "מוצר חדש"
        )

        assert source == "none"
        assert item is None


class TestCanonicalKeyAutoMerge:
    """End-to-end: a new purchase that hits the canonical_key path triggers an
    auto-merge into an existing list item, and the counter is bumped."""

    @pytest.mark.anyio
    @patch("app.services.product_matcher.calculate_refresh_for_item")
    async def test_canonical_match_increments_auto_merged_counter(
        self, mock_refresh: AsyncMock
    ) -> None:
        mock_refresh.return_value = (7, 0.4, None)

        db = AsyncMock(spec=AsyncSession)

        # Existing list item with canonical_key set
        existing_item = _mock_list_item(name="עגבניות שרי", status="active")
        existing_item.canonical_key = "עגבניות שרי"
        existing_item.product_id = None  # Not linked to the new product yet

        # The new purchase brings a different product (e.g. "עגבניות שרי פרימיום")
        new_product = _mock_product(name="עגבניות שרי פרימיום")
        new_product.id = uuid.uuid4()

        purchase = _mock_purchase(
            raw_name="עגבניות שרי פרימיום", barcode=None,
        )

        receipt = MagicMock()
        receipt.id = uuid.uuid4()

        # Sequence:
        # 1. exact_name lookup -> None (purchase.barcode is None, so skip barcode)
        # 2. fuzzy_sku scan -> empty (no products in DB yet)
        # 3. After Product creation: alias lookup -> None
        # 4. direct active -> None
        # 5. direct any -> None
        # 6. canonical_key lookup -> existing_item (THIS IS THE WIN)
        exact_name_result = MagicMock()
        exact_name_result.scalar_one_or_none.return_value = None

        fuzzy_result = MagicMock()
        fuzzy_result.scalars.return_value.all.return_value = []

        alias_result = MagicMock()
        alias_result.scalar_one_or_none.return_value = None

        direct_active_result = MagicMock()
        direct_active_result.scalar_one_or_none.return_value = None

        direct_any_result = MagicMock()
        direct_any_result.scalar_one_or_none.return_value = None

        canonical_result = MagicMock()
        canonical_result.scalar_one_or_none.return_value = existing_item

        db.execute.side_effect = [
            exact_name_result,
            fuzzy_result,
            alias_result,
            direct_active_result,
            direct_any_result,
            canonical_result,
        ]

        # Track the new product creation
        added_objects: list[Any] = []

        def track_add(obj: Any) -> None:
            obj.id = obj.id if getattr(obj, "id", None) else uuid.uuid4()
            added_objects.append(obj)

        db.add.side_effect = track_add

        counts = await match_receipt_purchases(
            db,
            receipt,
            FAKE_USER_ID,
            purchases=[purchase],
            canonicals=["עגבניות שרי"],
        )

        assert counts["new"] == 1  # New product was created
        assert counts["completed_items"] == 1
        assert counts["auto_merged_to_existing"] == 1  # The new counter
        assert existing_item.status == "completed"
        assert existing_item.last_completed_at is not None
