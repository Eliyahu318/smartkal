"""Tests for the canonicalizer service.

The negative-case suite is the most important part of this file: a canonicalizer
that over-merges (e.g. collapses חלב 1% into חלב 3%) is worse than no canonicalizer
at all, because it would silently destroy distinct items on a user's list.
"""

from __future__ import annotations

import pytest

from app.services.canonicalizer import canonical_key


# ---------------------------------------------------------------------------
# Positive cases — variants that SHOULD collapse to the same canonical key
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("a", "b"),
    [
        # The motivating example from the user
        ("עגבניות שרי", "עגבניות שרי פרימיום"),
        ("עגבניות שרי", "עגבניות שרי עגול"),
        ("עגבניות שרי פרימיום", "עגבניות שרי עגול"),
        # Brand stripping
        ("חלב 3%", "חלב תנובה 3%"),
        ("יוגורט", "יוגורט שטראוס"),
        # Size / unit stripping
        ("עגבניות שרי", "עגבניות שרי 250 גרם"),
        ("חלב 3%", "חלב 3% 1 ליטר"),
        ("חלב 3%", 'חלב 3% 1 ל"'),
        ("קמח", "קמח 1 ק\"ג"),
        ("קמח", "קמח 1 קג"),
        # Shape / form variants
        ("גזר", "גזר חתוך"),
        ("גזר", "גזר מגורד"),
        ("מלפפון", "מלפפון קטן"),
        ("מלפפון", "מלפפון בינוני"),
        # Quality markers
        ("שמן זית", "שמן זית מובחר"),
        ("שמן זית", "שמן זית פרימיום"),
        # Combined: brand + size + quality + shape
        (
            "עגבניות שרי",
            "עגבניות שרי פרימיום תנובה 250 גרם עגול",
        ),
    ],
)
def test_canonical_key_positive_pairs(a: str, b: str) -> None:
    """Two variants of the same conceptual item must produce the same key."""
    assert canonical_key(a) == canonical_key(b), (
        f"expected canonical_key({a!r}) == canonical_key({b!r}), "
        f"got {canonical_key(a)!r} vs {canonical_key(b)!r}"
    )


# ---------------------------------------------------------------------------
# Negative cases — these MUST stay distinct (the most critical tests)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("a", "b"),
    [
        # Fat percentages — different products
        ("חלב 1%", "חלב 3%"),
        ("חלב 3%", "חלב 5%"),
        ("יוגורט 0%", "יוגורט 3%"),
        ("קוטג' 5%", "קוטג' 9%"),
        # Diet / sugar markers
        ("קוקה קולה", "קוקה קולה זירו"),
        ("קוקה קולה", "קוקה קולה לייט"),
        ("קוקה קולה זירו", "קוקה קולה לייט"),
        ("שוקולד", "שוקולד ללא סוכר"),
        # Plant milk vs dairy
        ("חלב פרה", "חלב סויה"),
        ("חלב", "חלב סויה"),
        ("חלב", "חלב שקדים"),
        ("חלב סויה", "חלב שקדים"),
        ("חלב", "חלב שיבולת שועל"),
        # Flavors
        ("יוגורט", "יוגורט וניל"),
        ("יוגורט וניל", "יוגורט שוקולד"),
        ("גלידה", "גלידה תות"),
        ("גלידה תות", "גלידה וניל"),
        # Different products that share a word
        ("לחם", "לחמניות"),
        ("עגבניות", "עגבניות שרי"),
        ("גבינה", "גבינה צהובה"),
        ("גבינה", "גבינה לבנה"),
        ("גבינה צהובה", "גבינה לבנה"),
        # Greek vs regular yogurt
        ("יוגורט", "יוגורט יווני"),
    ],
)
def test_canonical_key_negative_pairs(a: str, b: str) -> None:
    """Distinct products MUST NOT collapse to the same canonical key."""
    assert canonical_key(a) != canonical_key(b), (
        f"FALSE POSITIVE: canonical_key({a!r}) == canonical_key({b!r}) == "
        f"{canonical_key(a)!r}"
    )


# ---------------------------------------------------------------------------
# Specific expected outputs for the most important cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected_substring"),
    [
        ("עגבניות שרי פרימיום תנובה 250 גרם", "עגבניות שרי"),
        ("חלב תנובה 3% 1 ליטר", "חלב 3%"),
        ('חלב תנובה 3% 1 ל"', "חלב 3%"),
        ("יוגורט פרימיום וניל 150 גרם", "יוגורט וניל"),
    ],
)
def test_canonical_key_specific_outputs(raw: str, expected_substring: str) -> None:
    """The canonical key should match the expected core string."""
    result = canonical_key(raw)
    assert expected_substring in result, (
        f"canonical_key({raw!r}) = {result!r}, expected to contain {expected_substring!r}"
    )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_canonical_key_empty_string() -> None:
    assert canonical_key("") == ""


def test_canonical_key_whitespace_only() -> None:
    assert canonical_key("   ") == ""


def test_canonical_key_strips_nikud() -> None:
    """Should reuse normalize_hebrew_name to strip nikud."""
    with_nikud = "עַגְבּנִיּוֹת שׁרִי"
    without_nikud = "עגבניות שרי"
    assert canonical_key(with_nikud) == canonical_key(without_nikud)


def test_canonical_key_fallback_when_everything_stripped() -> None:
    """If stopword stripping produces an empty string, fall back to normalized name.

    Otherwise we'd over-merge: a name that consists only of stopwords (e.g. just
    "פרימיום מובחר") would become "" and then collide with every other empty name.
    """
    result = canonical_key("פרימיום מובחר")
    # Must not be empty — fallback should kick in
    assert len(result) >= 2


def test_canonical_key_preserves_percent() -> None:
    """The % character is essential for distinguishing fat content."""
    assert "3%" in canonical_key("חלב 3% תנובה")
    assert "1%" in canonical_key("חלב 1% תנובה")


def test_canonical_key_preserves_flavors() -> None:
    """Flavor words must survive the stripping pass."""
    assert "וניל" in canonical_key("יוגורט וניל פרימיום")
    assert "שוקולד" in canonical_key("גלידה שוקולד תנובה 500 גרם")


def test_canonical_key_idempotent() -> None:
    """canonical_key should be a fixed point: f(f(x)) == f(x)."""
    raw = "עגבניות שרי פרימיום תנובה 250 גרם עגול"
    once = canonical_key(raw)
    twice = canonical_key(once)
    assert once == twice


def test_canonical_key_pure_function() -> None:
    """Same input → same output, no hidden state."""
    raw = "חלב תנובה 3% 1 ליטר"
    results = [canonical_key(raw) for _ in range(5)]
    assert all(r == results[0] for r in results)


# ---------------------------------------------------------------------------
# extract_canonical_names_claude — batched Claude fallback
# ---------------------------------------------------------------------------

import json  # noqa: E402
from types import SimpleNamespace  # noqa: E402
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402

import pytest  # noqa: E402

from app.services.canonicalizer import extract_canonical_names_claude  # noqa: E402


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _make_claude_response(items: list[str]) -> SimpleNamespace:
    """Build a fake Anthropic response with the given canonical names."""
    text = json.dumps({"items": items}, ensure_ascii=False)
    block = SimpleNamespace(type="text", text=text)
    return SimpleNamespace(content=[block], stop_reason="end_turn")


class TestExtractCanonicalNamesClaude:
    @pytest.mark.anyio
    async def test_empty_list_returns_empty(self) -> None:
        """No work to do — should not call the API."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            result = await extract_canonical_names_claude([])
        assert result == []

    @pytest.mark.anyio
    async def test_no_api_key_returns_nones(self) -> None:
        """Without an API key, returns a list of Nones (silent fallback)."""
        with patch.dict("os.environ", {}, clear=True):
            result = await extract_canonical_names_claude(["עגבניות שרי פרימיום"])
        assert result == [None]

    @pytest.mark.anyio
    async def test_successful_batch_extraction(self) -> None:
        """Claude returns canonical names — function unwraps the JSON correctly."""
        fake_response = _make_claude_response(
            ["עגבניות שרי", "חלב 3%", "לחם"]
        )
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=fake_response)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch(
                "app.services.canonicalizer.anthropic.AsyncAnthropic",
                return_value=mock_client,
            ):
                result = await extract_canonical_names_claude(
                    [
                        "עגבניות שרי פרימיום תנובה",
                        "חלב תנובה 3% 1 ליטר",
                        "לחם אחיד אסם",
                    ]
                )

        assert result == ["עגבניות שרי", "חלב 3%", "לחם"]
        mock_client.messages.create.assert_awaited_once()

    @pytest.mark.anyio
    async def test_handles_markdown_fences(self) -> None:
        """Claude wrapping JSON in ```json fences should still parse."""
        text = '```json\n{"items": ["עגבניות שרי"]}\n```'
        block = SimpleNamespace(type="text", text=text)
        fake_response = SimpleNamespace(content=[block], stop_reason="end_turn")

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=fake_response)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch(
                "app.services.canonicalizer.anthropic.AsyncAnthropic",
                return_value=mock_client,
            ):
                result = await extract_canonical_names_claude(["עגבניות שרי פרימיום"])

        assert result == ["עגבניות שרי"]

    @pytest.mark.anyio
    async def test_invalid_json_returns_nones(self) -> None:
        """Malformed JSON falls back to Nones for the whole batch."""
        block = SimpleNamespace(type="text", text="not valid json {{{{")
        fake_response = SimpleNamespace(content=[block], stop_reason="end_turn")

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=fake_response)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch(
                "app.services.canonicalizer.anthropic.AsyncAnthropic",
                return_value=mock_client,
            ):
                result = await extract_canonical_names_claude(["עגבניות שרי", "חלב"])

        assert result == [None, None]

    @pytest.mark.anyio
    async def test_shape_mismatch_returns_nones(self) -> None:
        """Claude returns wrong number of items → fall back to Nones."""
        fake_response = _make_claude_response(["עגבניות שרי"])  # only 1
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=fake_response)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch(
                "app.services.canonicalizer.anthropic.AsyncAnthropic",
                return_value=mock_client,
            ):
                result = await extract_canonical_names_claude(
                    ["עגבניות שרי פרימיום", "חלב 3%"]  # asked for 2
                )

        assert result == [None, None]

    @pytest.mark.anyio
    async def test_api_error_returns_nones(self) -> None:
        """Anthropic APIError → fall back to Nones for that batch."""
        import anthropic

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            side_effect=anthropic.APIError(
                message="boom",
                request=MagicMock(),
                body=None,
            )
        )

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch(
                "app.services.canonicalizer.anthropic.AsyncAnthropic",
                return_value=mock_client,
            ):
                result = await extract_canonical_names_claude(["עגבניות שרי"])

        assert result == [None]

    @pytest.mark.anyio
    async def test_empty_string_in_response_becomes_none(self) -> None:
        """Empty string entries in Claude's response become None."""
        fake_response = _make_claude_response(["עגבניות שרי", "", "  "])
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=fake_response)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch(
                "app.services.canonicalizer.anthropic.AsyncAnthropic",
                return_value=mock_client,
            ):
                result = await extract_canonical_names_claude(
                    ["עגבניות שרי פרימיום", "מוצר 1", "מוצר 2"]
                )

        assert result == ["עגבניות שרי", None, None]

    @pytest.mark.anyio
    async def test_batches_large_input(self) -> None:
        """Inputs over BATCH_SIZE are split into multiple Claude calls."""
        # Generate 25 names → expects 2 batches (20 + 5)
        names = [f"מוצר {i} פרימיום" for i in range(25)]
        canonical_per_batch_1 = [f"מוצר {i}" for i in range(20)]
        canonical_per_batch_2 = [f"מוצר {i}" for i in range(20, 25)]

        fake_responses = [
            _make_claude_response(canonical_per_batch_1),
            _make_claude_response(canonical_per_batch_2),
        ]
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=fake_responses)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch(
                "app.services.canonicalizer.anthropic.AsyncAnthropic",
                return_value=mock_client,
            ):
                result = await extract_canonical_names_claude(names)

        assert len(result) == 25
        assert result[0] == "מוצר 0"
        assert result[24] == "מוצר 24"
        assert mock_client.messages.create.await_count == 2
