"""Tests for item_merger service.

Focuses on the validation and orchestration paths. The deeper mechanics
(alias UPSERT, refresh recalculation, JSON serialization) are exercised by
the API-level tests in test_list.py and the E2E suite.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.services.item_merger import (
    DuplicateGroup,
    _group_is_safe_for_auto_merge,
    _serialize_list_item,
    find_duplicate_groups,
    merge_list_items,
)


FAKE_USER_ID = uuid.uuid4()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _mock_list_item(
    item_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    name: str = "עגבניות שרי",
    canonical_key: str | None = "עגבניות שרי",
    product_id: uuid.UUID | None = None,
    note: str | None = None,
) -> MagicMock:
    now = datetime.now(timezone.utc)
    item = MagicMock()
    item.id = item_id or uuid.uuid4()
    item.user_id = user_id or FAKE_USER_ID
    item.product_id = product_id
    item.category_id = None
    item.name = name
    item.canonical_key = canonical_key
    item.quantity = None
    item.note = note
    item.status = "active"
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


# ---------------------------------------------------------------------------
# find_duplicate_groups
# ---------------------------------------------------------------------------


class TestFindDuplicateGroups:
    @pytest.mark.anyio
    async def test_groups_items_by_canonical_key(self) -> None:
        a1 = _mock_list_item(name="עגבניות שרי", canonical_key="עגבניות שרי")
        a2 = _mock_list_item(name="עגבניות שרי פרימיום", canonical_key="עגבניות שרי")
        b = _mock_list_item(name="חלב 3%", canonical_key="חלב 3%")  # singleton, ignored

        db = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalars.return_value.all.return_value = [a1, a2, b]
        db.execute.return_value = result

        groups = await find_duplicate_groups(db, FAKE_USER_ID)

        assert len(groups) == 1
        assert groups[0].canonical == "עגבניות שרי"
        assert {i.id for i in groups[0].items} == {a1.id, a2.id}

    @pytest.mark.anyio
    async def test_excludes_singletons(self) -> None:
        a = _mock_list_item(canonical_key="חלב 3%")
        b = _mock_list_item(canonical_key="לחם")

        db = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalars.return_value.all.return_value = [a, b]
        db.execute.return_value = result

        groups = await find_duplicate_groups(db, FAKE_USER_ID)
        assert groups == []

    @pytest.mark.anyio
    async def test_skips_items_without_canonical_key(self) -> None:
        a = _mock_list_item(canonical_key="עגבניות שרי")
        b = _mock_list_item(canonical_key=None)
        c = _mock_list_item(canonical_key="")

        db = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalars.return_value.all.return_value = [a, b, c]
        db.execute.return_value = result

        groups = await find_duplicate_groups(db, FAKE_USER_ID)
        assert groups == []  # Only one item with a real canonical_key


# ---------------------------------------------------------------------------
# _group_is_safe_for_auto_merge
# ---------------------------------------------------------------------------


class TestSafeForAutoMerge:
    def test_two_similar_names_pass(self) -> None:
        a = _mock_list_item(name="עגבניות שרי", canonical_key="עגבניות שרי")
        b = _mock_list_item(name="עגבניות שרי פרימיום", canonical_key="עגבניות שרי")
        group = DuplicateGroup(canonical="עגבניות שרי", items=[a, b])

        assert _group_is_safe_for_auto_merge(group) is True

    def test_two_unrelated_names_fail(self) -> None:
        # If canonicalizer somehow over-merged, the safety check catches it.
        a = _mock_list_item(name="חלב פרה", canonical_key="חלב")
        b = _mock_list_item(name="חלב סויה אורגני שטראוס", canonical_key="חלב")
        group = DuplicateGroup(canonical="חלב", items=[a, b])

        assert _group_is_safe_for_auto_merge(group) is False

    def test_singleton_returns_false(self) -> None:
        a = _mock_list_item(canonical_key="עגבניות שרי")
        group = DuplicateGroup(canonical="עגבניות שרי", items=[a])
        assert _group_is_safe_for_auto_merge(group) is False


# ---------------------------------------------------------------------------
# _serialize_list_item
# ---------------------------------------------------------------------------


class TestSerializeListItem:
    def test_includes_essential_fields(self) -> None:
        item = _mock_list_item(name="עגבניות שרי", note="קופסה")
        item.product_id = uuid.uuid4()
        item.category_id = uuid.uuid4()

        payload = _serialize_list_item(item)

        assert payload["name"] == "עגבניות שרי"
        assert payload["note"] == "קופסה"
        assert payload["canonical_key"] == "עגבניות שרי"
        assert payload["product_id"] == str(item.product_id)
        assert payload["category_id"] == str(item.category_id)
        assert payload["id"] == str(item.id)


# ---------------------------------------------------------------------------
# merge_list_items — validation paths
# ---------------------------------------------------------------------------


class TestMergeValidation:
    @pytest.mark.anyio
    async def test_empty_source_ids_raises(self) -> None:
        db = AsyncMock(spec=AsyncSession)
        with pytest.raises(ValidationError):
            await merge_list_items(db, FAKE_USER_ID, uuid.uuid4(), [])

    @pytest.mark.anyio
    async def test_target_in_sources_raises(self) -> None:
        db = AsyncMock(spec=AsyncSession)
        target_id = uuid.uuid4()
        with pytest.raises(ValidationError):
            await merge_list_items(
                db, FAKE_USER_ID, target_id, [uuid.uuid4(), target_id]
            )

    @pytest.mark.anyio
    async def test_target_not_owned_raises(self) -> None:
        db = AsyncMock(spec=AsyncSession)
        # _load_owned_items returns empty (length mismatch -> NotFoundError)
        empty_result = MagicMock()
        empty_result.scalars.return_value.all.return_value = []
        db.execute.return_value = empty_result

        with pytest.raises(NotFoundError):
            await merge_list_items(
                db, FAKE_USER_ID, uuid.uuid4(), [uuid.uuid4()]
            )

    @pytest.mark.anyio
    async def test_source_not_owned_raises(self) -> None:
        db = AsyncMock(spec=AsyncSession)
        # First execute (target lookup) returns the target item
        target = _mock_list_item()
        target_result = MagicMock()
        target_result.scalars.return_value.all.return_value = [target]

        # Second execute (sources) returns empty -> length mismatch
        sources_result = MagicMock()
        sources_result.scalars.return_value.all.return_value = []

        db.execute.side_effect = [target_result, sources_result]

        with pytest.raises(NotFoundError):
            await merge_list_items(
                db, FAKE_USER_ID, target.id, [uuid.uuid4()]
            )


# ---------------------------------------------------------------------------
# merge_list_items — happy-path mechanics
# ---------------------------------------------------------------------------


class TestMergeMechanics:
    @pytest.mark.anyio
    @patch("app.services.item_merger.calculate_refresh_for_item")
    async def test_full_merge_writes_audit_log_and_aliases(
        self, mock_refresh: AsyncMock
    ) -> None:
        """End-to-end merge: snapshots written, aliases upserted, sources deleted,
        notes merged, refresh recalculated, target returned."""
        from datetime import timedelta

        from app.services.item_merger import merge_list_items

        mock_refresh.return_value = (10, 0.5, None)

        target_product_id = uuid.uuid4()
        source1_product_id = uuid.uuid4()
        source2_product_id = uuid.uuid4()

        target = _mock_list_item(
            name="עגבניות שרי", note="היכן ששרון אוהבת"
        )
        target.product_id = target_product_id
        target.created_at = datetime.now(timezone.utc) - timedelta(days=10)

        source1 = _mock_list_item(
            name="עגבניות שרי פרימיום", note="פרימיום"
        )
        source1.id = uuid.uuid4()
        source1.product_id = source1_product_id
        source1.created_at = datetime.now(timezone.utc) - timedelta(days=20)
        source1.last_completed_at = datetime.now(timezone.utc) - timedelta(days=2)

        source2 = _mock_list_item(name="עגבניות שרי עגול", note=None)
        source2.id = uuid.uuid4()
        source2.product_id = source2_product_id
        source2.created_at = datetime.now(timezone.utc) - timedelta(days=5)

        db = AsyncMock(spec=AsyncSession)

        # Sequence of execute calls:
        # 1. _load_owned_items target -> [target]
        target_result = MagicMock()
        target_result.scalars.return_value.all.return_value = [target]
        # 2. _load_owned_items sources -> [source1, source2]
        sources_result = MagicMock()
        sources_result.scalars.return_value.all.return_value = [source1, source2]
        # 3. existing aliases pointing to sources -> empty
        existing_aliases_result = MagicMock()
        existing_aliases_result.scalars.return_value.all.return_value = []
        # 4-5. Two pg_insert ON CONFLICT statements (one per product) — return None
        upsert_1 = MagicMock()
        upsert_2 = MagicMock()

        db.execute.side_effect = [
            target_result,
            sources_result,
            existing_aliases_result,
            upsert_1,
            upsert_2,
        ]

        added_logs: list[Any] = []
        db.add.side_effect = lambda obj: added_logs.append(obj)

        deleted: list[Any] = []
        db.delete = AsyncMock(side_effect=lambda obj: deleted.append(obj))

        result = await merge_list_items(
            db, FAKE_USER_ID, target.id, [source1.id, source2.id]
        )

        # Audit: one log row per source
        assert len(added_logs) == 2
        log1 = added_logs[0]
        assert log1.source_name == "עגבניות שרי פרימיום"
        assert log1.target_id == target.id
        # Snapshot is JSON-serializable
        assert log1.source_payload["name"] == "עגבניות שרי פרימיום"
        assert log1.source_payload["note"] == "פרימיום"

        # Both sources were deleted
        assert len(deleted) == 2
        assert source1 in deleted
        assert source2 in deleted

        # Notes were merged with " · "
        assert "היכן ששרון אוהבת" in (target.note or "")
        assert "פרימיום" in (target.note or "")

        # created_at took the earliest of the three (source1)
        assert target.created_at == source1.created_at

        # last_completed_at took the latest (source1's)
        assert target.last_completed_at == source1.last_completed_at

        # Refresh was recalculated
        mock_refresh.assert_awaited()
        assert target.system_refresh_days == 10
        assert target.confidence == 0.5

        # The target is returned
        assert result is target

    @pytest.mark.anyio
    @patch("app.services.item_merger.calculate_refresh_for_item")
    async def test_merge_with_no_product_ids_skips_alias_upserts(
        self, mock_refresh: AsyncMock
    ) -> None:
        """Sources without product_id don't trigger alias upserts."""
        from app.services.item_merger import merge_list_items

        mock_refresh.return_value = (None, None, None)

        target = _mock_list_item(name="עגבניות שרי")
        target.product_id = None

        source = _mock_list_item(name="עגבניות שרי פרימיום")
        source.id = uuid.uuid4()
        source.product_id = None  # Manual item, no product link

        db = AsyncMock(spec=AsyncSession)

        target_result = MagicMock()
        target_result.scalars.return_value.all.return_value = [target]
        sources_result = MagicMock()
        sources_result.scalars.return_value.all.return_value = [source]
        existing_aliases_result = MagicMock()
        existing_aliases_result.scalars.return_value.all.return_value = []

        db.execute.side_effect = [
            target_result,
            sources_result,
            existing_aliases_result,
        ]
        db.add.side_effect = lambda obj: None
        db.delete = AsyncMock()

        await merge_list_items(db, FAKE_USER_ID, target.id, [source.id])

        # Only the 3 expected execute calls — no alias upsert calls
        assert db.execute.call_count == 3


# ---------------------------------------------------------------------------
# auto_merge_safe_groups
# ---------------------------------------------------------------------------


class TestAutoMergeSafeGroups:
    @pytest.mark.anyio
    async def test_no_groups_returns_zero(self) -> None:
        from app.services.item_merger import auto_merge_safe_groups

        db = AsyncMock(spec=AsyncSession)
        empty_result = MagicMock()
        empty_result.scalars.return_value.all.return_value = []
        db.execute.return_value = empty_result

        merged_count, group_count = await auto_merge_safe_groups(db, FAKE_USER_ID)

        assert merged_count == 0
        assert group_count == 0

    @pytest.mark.anyio
    async def test_unsafe_group_is_skipped(self) -> None:
        """A group whose items don't meet the secondary similarity threshold
        is left untouched."""
        from app.services.item_merger import auto_merge_safe_groups

        # Two items with same canonical_key but very different names
        a = _mock_list_item(name="חלב פרה")
        a.canonical_key = "חלב"
        b = _mock_list_item(name="חלב סויה אורגני שטראוס דל סוכר")
        b.canonical_key = "חלב"
        b.id = uuid.uuid4()

        db = AsyncMock(spec=AsyncSession)
        find_result = MagicMock()
        find_result.scalars.return_value.all.return_value = [a, b]
        db.execute.return_value = find_result

        merged_count, group_count = await auto_merge_safe_groups(db, FAKE_USER_ID)

        # Group exists in raw form but is not safe → skipped
        assert merged_count == 0
        assert group_count == 0
