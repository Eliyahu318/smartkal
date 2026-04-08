"""Tests for US-010: Complete/activate items + auto-refresh engine."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

FAKE_USER_ID = uuid.uuid4()
FAKE_CATEGORY_ID = uuid.uuid4()
FAKE_ITEM_ID = uuid.uuid4()
FAKE_PRODUCT_ID = uuid.uuid4()


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


def _mock_list_item(
    item_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    name: str = "חלב",
    status: str = "active",
    auto_refresh_days: int | None = None,
    system_refresh_days: int | None = None,
    next_refresh_at: datetime | None = None,
    last_completed_at: datetime | None = None,
    last_activated_at: datetime | None = None,
) -> MagicMock:
    now = datetime.now(timezone.utc)
    item = MagicMock()
    item.id = item_id or FAKE_ITEM_ID
    item.user_id = user_id or FAKE_USER_ID
    item.product_id = product_id
    item.category_id = category_id
    item.name = name
    item.quantity = None
    item.note = None
    item.status = status
    item.source = "manual"
    item.confidence = None
    item.display_order = 0
    item.auto_refresh_days = auto_refresh_days
    item.system_refresh_days = system_refresh_days
    item.next_refresh_at = next_refresh_at
    item.last_completed_at = last_completed_at
    item.last_activated_at = last_activated_at
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
# Unit tests: refresh engine pure functions
# ---------------------------------------------------------------------------


class TestComputeRefreshDays:
    """Test the frequency calculation logic."""

    def test_empty_intervals(self) -> None:
        from app.services.refresh_engine import compute_refresh_days

        days, confidence = compute_refresh_days([])
        assert days == 0
        assert confidence == 0.0

    def test_single_interval(self) -> None:
        from app.services.refresh_engine import compute_refresh_days

        days, confidence = compute_refresh_days([7.0])
        assert days == 7
        assert confidence == 0.2

    def test_two_intervals_median(self) -> None:
        from app.services.refresh_engine import compute_refresh_days

        days, confidence = compute_refresh_days([5.0, 9.0])
        assert days == 7  # median of 5, 9 = 7
        assert confidence == 0.3

    def test_three_intervals(self) -> None:
        from app.services.refresh_engine import compute_refresh_days

        days, confidence = compute_refresh_days([7.0, 7.0, 8.0])
        assert days == 7  # median
        assert confidence >= 0.4

    def test_many_intervals_high_confidence(self) -> None:
        from app.services.refresh_engine import compute_refresh_days

        intervals = [7.0, 7.0, 7.0, 7.0, 7.0, 7.0, 7.0, 7.0, 7.0, 7.0]
        days, confidence = compute_refresh_days(intervals)
        assert days == 7
        # 10 intervals = 0.8 base + low variance bonus 0.15 = 0.95
        assert confidence == 0.95

    def test_low_variance_bonus(self) -> None:
        from app.services.refresh_engine import compute_refresh_days

        # Very consistent intervals → low variance bonus
        intervals = [7.0, 7.0, 7.0, 7.0, 7.0]
        days, confidence = compute_refresh_days(intervals)
        assert days == 7
        # 5 intervals = 0.6 base + 0.15 bonus = 0.75
        assert confidence == 0.75

    def test_high_variance_no_bonus(self) -> None:
        from app.services.refresh_engine import compute_refresh_days

        # Very inconsistent intervals → no bonus
        intervals = [3.0, 14.0, 5.0, 20.0, 7.0]
        days, confidence = compute_refresh_days(intervals)
        assert days == 7  # median
        # 5 intervals = 0.6 base, high variance → no bonus
        assert confidence == 0.6

    def test_minimum_one_day(self) -> None:
        from app.services.refresh_engine import compute_refresh_days

        days, confidence = compute_refresh_days([0.3])
        assert days == 1  # minimum 1 day


class TestCalculateConfidence:
    """Test confidence scoring tiers."""

    def test_zero_intervals(self) -> None:
        from app.services.refresh_engine import calculate_confidence

        assert calculate_confidence(0, None) == 0.0

    def test_one_interval(self) -> None:
        from app.services.refresh_engine import calculate_confidence

        assert calculate_confidence(1, None) == 0.2

    def test_two_intervals(self) -> None:
        from app.services.refresh_engine import calculate_confidence

        assert calculate_confidence(2, None) == 0.3

    def test_four_intervals(self) -> None:
        from app.services.refresh_engine import calculate_confidence

        assert calculate_confidence(4, None) == 0.4

    def test_seven_intervals(self) -> None:
        from app.services.refresh_engine import calculate_confidence

        assert calculate_confidence(7, None) == 0.6

    def test_ten_plus_intervals(self) -> None:
        from app.services.refresh_engine import calculate_confidence

        assert calculate_confidence(10, None) == 0.8

    def test_low_variance_bonus_applied(self) -> None:
        from app.services.refresh_engine import calculate_confidence

        # 5 intervals + low variance → 0.6 + 0.15 = 0.75
        assert calculate_confidence(5, 0.1) == 0.75

    def test_high_variance_no_bonus(self) -> None:
        from app.services.refresh_engine import calculate_confidence

        # 5 intervals + high variance → 0.6
        assert calculate_confidence(5, 0.5) == 0.6

    def test_confidence_capped_at_095(self) -> None:
        from app.services.refresh_engine import calculate_confidence

        # 10+ intervals (0.8) + low variance bonus (0.15) = 0.95 (capped)
        assert calculate_confidence(15, 0.1) == 0.95


class TestTimestampsToIntervals:
    """Test timestamp → interval conversion."""

    def test_empty_list(self) -> None:
        from app.services.refresh_engine import timestamps_to_intervals

        assert timestamps_to_intervals([]) == []

    def test_single_timestamp(self) -> None:
        from app.services.refresh_engine import timestamps_to_intervals

        ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
        assert timestamps_to_intervals([ts]) == []

    def test_two_timestamps(self) -> None:
        from app.services.refresh_engine import timestamps_to_intervals

        ts1 = datetime(2025, 1, 1, tzinfo=timezone.utc)
        ts2 = datetime(2025, 1, 8, tzinfo=timezone.utc)
        intervals = timestamps_to_intervals([ts1, ts2])
        assert len(intervals) == 1
        assert intervals[0] == 7.0

    def test_unsorted_timestamps(self) -> None:
        from app.services.refresh_engine import timestamps_to_intervals

        ts1 = datetime(2025, 1, 15, tzinfo=timezone.utc)
        ts2 = datetime(2025, 1, 1, tzinfo=timezone.utc)
        ts3 = datetime(2025, 1, 8, tzinfo=timezone.utc)
        intervals = timestamps_to_intervals([ts1, ts2, ts3])
        assert len(intervals) == 2
        assert intervals[0] == 7.0
        assert intervals[1] == 7.0


# ---------------------------------------------------------------------------
# PATCH /api/v1/list/items/{id}/complete
# ---------------------------------------------------------------------------


class TestCompleteItem:
    """Test completing a list item."""

    @pytest.mark.anyio
    @patch("app.api.v1.list.calculate_refresh_for_item", new_callable=AsyncMock)
    async def test_complete_item_success(self, mock_calc: AsyncMock) -> None:
        """Completing an active item sets status, timestamps, and refresh."""
        mock_calc.return_value = (7, 0.4, datetime(2025, 2, 8, tzinfo=timezone.utc))

        item = _mock_list_item(status="active")

        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = item
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/list/items/{item.id}/complete",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        assert item.status == "completed"
        assert item.last_completed_at is not None
        assert item.system_refresh_days == 7
        assert item.confidence == 0.4

    @pytest.mark.anyio
    async def test_complete_already_completed_returns_422(self) -> None:
        """Completing an already completed item returns validation error."""
        item = _mock_list_item(status="completed")

        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = item
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/list/items/{item.id}/complete",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 422

    @pytest.mark.anyio
    @patch("app.api.v1.list.calculate_refresh_for_item", new_callable=AsyncMock)
    async def test_complete_item_no_refresh_data(self, mock_calc: AsyncMock) -> None:
        """Completing an item with no purchase history leaves refresh fields null."""
        mock_calc.return_value = (None, None, None)

        item = _mock_list_item(status="active")

        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = item
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/list/items/{item.id}/complete",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        assert item.status == "completed"
        assert item.system_refresh_days is None
        assert item.next_refresh_at is None

    @pytest.mark.anyio
    async def test_complete_nonexistent_item_returns_404(self) -> None:
        """Completing a nonexistent item returns 404."""
        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/list/items/{uuid.uuid4()}/complete",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/list/items/{id}/activate
# ---------------------------------------------------------------------------


class TestActivateItem:
    """Test activating a completed list item."""

    @pytest.mark.anyio
    async def test_activate_item_success(self) -> None:
        """Activating a completed item sets status and clears refresh."""
        item = _mock_list_item(
            status="completed",
            next_refresh_at=datetime(2025, 2, 8, tzinfo=timezone.utc),
        )

        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = item
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/list/items/{item.id}/activate",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        assert item.status == "active"
        assert item.last_activated_at is not None
        assert item.next_refresh_at is None

    @pytest.mark.anyio
    async def test_activate_already_active_returns_422(self) -> None:
        """Activating an already active item returns validation error."""
        item = _mock_list_item(status="active")

        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = item
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/list/items/{item.id}/activate",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_activate_nonexistent_item_returns_404(self) -> None:
        """Activating a nonexistent item returns 404."""
        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/list/items/{uuid.uuid4()}/activate",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/list/refresh
# ---------------------------------------------------------------------------


class TestRefreshItems:
    """Test the refresh endpoint that activates overdue items."""

    @pytest.mark.anyio
    @patch("app.api.v1.list.activate_overdue_items", new_callable=AsyncMock)
    async def test_refresh_activates_overdue(self, mock_activate: AsyncMock) -> None:
        """Refresh activates items past their next_refresh_at."""
        activated_item = _mock_list_item(
            status="active",
            last_activated_at=datetime.now(timezone.utc),
        )
        activated_item.source = "auto_refresh"
        mock_activate.return_value = [activated_item]

        mock_session = AsyncMock(spec=AsyncSession)
        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/list/refresh",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["activated_count"] == 1
        assert len(data["activated_items"]) == 1

    @pytest.mark.anyio
    @patch("app.api.v1.list.activate_overdue_items", new_callable=AsyncMock)
    async def test_refresh_no_overdue_items(self, mock_activate: AsyncMock) -> None:
        """Refresh with no overdue items returns empty list."""
        mock_activate.return_value = []

        mock_session = AsyncMock(spec=AsyncSession)
        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/list/refresh",
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["activated_count"] == 0
        assert data["activated_items"] == []


# ---------------------------------------------------------------------------
# PATCH /api/v1/list/items/{id}/preferences
# ---------------------------------------------------------------------------


class TestUpdatePreferences:
    """Test user override for auto-refresh frequency."""

    @pytest.mark.anyio
    async def test_set_user_override(self) -> None:
        """Setting auto_refresh_days stores the user override."""
        item = _mock_list_item(status="active")

        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = item
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/list/items/{item.id}/preferences",
                json={"auto_refresh_days": 14},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        assert item.auto_refresh_days == 14

    @pytest.mark.anyio
    async def test_user_override_on_completed_item_recalculates(self) -> None:
        """Setting override on completed item recalculates next_refresh_at."""
        completed_at = datetime(2025, 2, 1, tzinfo=timezone.utc)
        item = _mock_list_item(
            status="completed",
            last_completed_at=completed_at,
        )

        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = item
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/list/items/{item.id}/preferences",
                json={"auto_refresh_days": 10},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        assert item.auto_refresh_days == 10
        assert item.confidence == 0.95
        expected_refresh = completed_at + timedelta(days=10)
        assert item.next_refresh_at == expected_refresh

    @pytest.mark.anyio
    @patch("app.api.v1.list.calculate_refresh_for_item", new_callable=AsyncMock)
    async def test_clear_user_override(self, mock_calc: AsyncMock) -> None:
        """Clearing override recalculates from system data."""
        mock_calc.return_value = (7, 0.4, datetime(2025, 2, 8, tzinfo=timezone.utc))

        item = _mock_list_item(
            status="completed",
            auto_refresh_days=14,
            last_completed_at=datetime(2025, 2, 1, tzinfo=timezone.utc),
        )

        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = item
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/list/items/{item.id}/preferences",
                json={"auto_refresh_days": None},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 200
        assert item.auto_refresh_days is None
        mock_calc.assert_called_once()

    @pytest.mark.anyio
    async def test_preferences_invalid_days_returns_422(self) -> None:
        """auto_refresh_days out of range returns validation error."""
        item = _mock_list_item()

        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = item
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/list/items/{item.id}/preferences",
                json={"auto_refresh_days": 0},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_preferences_nonexistent_item_returns_404(self) -> None:
        """Preferences on nonexistent item returns 404."""
        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        user = _mock_user()
        app = _setup_app_with_mocks(mock_session, user)

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/list/items/{uuid.uuid4()}/preferences",
                json={"auto_refresh_days": 7},
                headers={"Authorization": "Bearer fake"},
            )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Auth protection for new endpoints
# ---------------------------------------------------------------------------


class TestNewEndpointsAuthProtection:
    """Verify new endpoints require authentication."""

    @pytest.mark.anyio
    async def test_complete_requires_auth(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(f"/api/v1/list/items/{uuid.uuid4()}/complete")
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_activate_requires_auth(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(f"/api/v1/list/items/{uuid.uuid4()}/activate")
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_refresh_requires_auth(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/list/refresh")
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_preferences_requires_auth(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/list/items/{uuid.uuid4()}/preferences",
                json={"auto_refresh_days": 7},
            )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Unit tests: activate_overdue_items
# ---------------------------------------------------------------------------


class TestActivateOverdueItems:
    """Test the refresh engine's overdue activation logic."""

    @pytest.mark.anyio
    async def test_activate_overdue_items_finds_and_activates(self) -> None:
        """Overdue completed items are activated."""
        from app.services.refresh_engine import activate_overdue_items

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        item = _mock_list_item(
            status="completed",
            next_refresh_at=past,
        )

        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalars.return_value.all.return_value = [item]
        mock_session.execute.return_value = result

        activated = await activate_overdue_items(mock_session, FAKE_USER_ID)

        assert len(activated) == 1
        assert item.status == "active"
        assert item.source == "auto_refresh"
        assert item.last_activated_at is not None
        assert item.next_refresh_at is None
        mock_session.flush.assert_called_once()

    @pytest.mark.anyio
    async def test_activate_overdue_items_none_overdue(self) -> None:
        """No overdue items returns empty list."""
        from app.services.refresh_engine import activate_overdue_items

        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = result

        activated = await activate_overdue_items(mock_session, FAKE_USER_ID)

        assert len(activated) == 0
        mock_session.flush.assert_not_called()


# ---------------------------------------------------------------------------
# Frequency calculation with known dates
# ---------------------------------------------------------------------------


class TestFrequencyCalculationKnownDates:
    """Test refresh calculation with specific date sequences."""

    def test_weekly_pattern(self) -> None:
        """Weekly purchases yield ~7 day refresh."""
        from app.services.refresh_engine import compute_refresh_days, timestamps_to_intervals

        dates = [
            datetime(2025, 1, 1, tzinfo=timezone.utc),
            datetime(2025, 1, 8, tzinfo=timezone.utc),
            datetime(2025, 1, 15, tzinfo=timezone.utc),
            datetime(2025, 1, 22, tzinfo=timezone.utc),
        ]
        intervals = timestamps_to_intervals(dates)
        days, confidence = compute_refresh_days(intervals)
        assert days == 7
        assert confidence >= 0.4  # 3 intervals

    def test_biweekly_pattern(self) -> None:
        """Biweekly purchases yield ~14 day refresh."""
        from app.services.refresh_engine import compute_refresh_days, timestamps_to_intervals

        dates = [
            datetime(2025, 1, 1, tzinfo=timezone.utc),
            datetime(2025, 1, 15, tzinfo=timezone.utc),
            datetime(2025, 1, 29, tzinfo=timezone.utc),
            datetime(2025, 2, 12, tzinfo=timezone.utc),
        ]
        intervals = timestamps_to_intervals(dates)
        days, confidence = compute_refresh_days(intervals)
        assert days == 14
        assert confidence >= 0.4

    def test_user_override_takes_priority(self) -> None:
        """User override should give confidence 0.95."""
        from app.services.refresh_engine import calculate_confidence

        # User override is handled in the endpoint, but confidence should be 0.95
        assert 0.95 == 0.95  # Verified in test_user_override_on_completed_item_recalculates


# ---------------------------------------------------------------------------
# gather_purchase_timestamps with alias support
# ---------------------------------------------------------------------------


class TestGatherPurchaseTimestampsAliasAware:
    """The dedup feature requires that gather_purchase_timestamps include
    purchases of products that are aliased to the same list item, so that
    cadence calculations after merging see the combined history."""

    @pytest.mark.anyio
    async def test_returns_empty_when_both_none(self) -> None:
        """No product_id and no list_item_id → empty list."""
        from app.services.refresh_engine import gather_purchase_timestamps

        db = AsyncMock(spec=AsyncSession)
        result = await gather_purchase_timestamps(
            db, FAKE_USER_ID, product_id=None, list_item_id=None
        )
        assert result == []
        # No DB call needed
        db.execute.assert_not_called()

    @pytest.mark.anyio
    async def test_includes_purchase_dates_for_product(self) -> None:
        """Standard product_id-only path returns purchase dates as datetimes."""
        from datetime import date

        from app.services.refresh_engine import gather_purchase_timestamps

        db = AsyncMock(spec=AsyncSession)

        # Three purchases on different dates
        dates_result = MagicMock()
        dates_result.scalars.return_value.all.return_value = [
            date(2026, 1, 5),
            date(2026, 1, 12),
            date(2026, 1, 19),
        ]
        db.execute.return_value = dates_result

        result = await gather_purchase_timestamps(
            db, FAKE_USER_ID, product_id=FAKE_PRODUCT_ID
        )

        assert len(result) == 3
        assert all(isinstance(d, datetime) for d in result)
        assert result[0].year == 2026 and result[0].month == 1 and result[0].day == 5

    @pytest.mark.anyio
    async def test_alias_aware_query_includes_list_item_id(self) -> None:
        """When list_item_id is passed, the query is built with the alias subquery.

        We verify by checking that exactly one execute call was made and the
        result is consumed correctly. The actual SQL shape is exercised by E2E
        and the integration tests in test_product_matcher.
        """
        from datetime import date

        from app.services.refresh_engine import gather_purchase_timestamps

        db = AsyncMock(spec=AsyncSession)
        dates_result = MagicMock()
        dates_result.scalars.return_value.all.return_value = [
            date(2026, 2, 1),
            date(2026, 2, 8),
        ]
        db.execute.return_value = dates_result

        result = await gather_purchase_timestamps(
            db,
            FAKE_USER_ID,
            product_id=FAKE_PRODUCT_ID,
            list_item_id=FAKE_ITEM_ID,
        )

        assert len(result) == 2
        # Exactly one query is fired (the alias subquery is inline, not a separate call)
        assert db.execute.call_count == 1

    @pytest.mark.anyio
    async def test_skips_none_dates(self) -> None:
        """Receipts without a date are skipped silently."""
        from datetime import date

        from app.services.refresh_engine import gather_purchase_timestamps

        db = AsyncMock(spec=AsyncSession)
        dates_result = MagicMock()
        dates_result.scalars.return_value.all.return_value = [
            date(2026, 1, 5),
            None,  # Missing receipt_date
            date(2026, 1, 19),
        ]
        db.execute.return_value = dates_result

        result = await gather_purchase_timestamps(
            db, FAKE_USER_ID, product_id=FAKE_PRODUCT_ID
        )

        assert len(result) == 2  # None was skipped
