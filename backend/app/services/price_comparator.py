"""SuperGET API client for Israeli supermarket price comparison.

Queries the SuperGET API to find product prices across Israeli supermarket chains.
Matches products by barcode first, then by fuzzy name match.
Saves price data to PriceHistory with source='superget'.

SuperGET API:
- Base URL: https://api.superget.co.il
- Auth: api_key parameter in POST body
- Request format: POST with action + api_key + additional params
- Response format: JSON
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import SuperGETError
from app.models.price_history import PriceHistory
from app.models.product import Product

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

SUPERGET_BASE_URL = "https://api.superget.co.il"
REQUEST_TIMEOUT = 15.0
MAX_RETRIES = 1


@dataclass
class StorePrice:
    """Price for a product at a specific store."""

    store_name: str
    store_branch: str | None
    price: Decimal
    product_name: str
    barcode: str | None = None


@dataclass
class ProductPriceResult:
    """Price comparison result for a single product."""

    product_id: uuid.UUID
    product_name: str
    prices: list[StorePrice] = field(default_factory=list)
    matched: bool = False


def _safe_decimal(value: object) -> Decimal | None:
    """Convert a value to Decimal, returning None on failure."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


async def _superget_request(
    action: str,
    params: dict[str, object] | None = None,
) -> dict[str, object]:
    """Make a POST request to the SuperGET API.

    Args:
        action: The API action/function name.
        params: Additional parameters for the request.

    Returns:
        Parsed JSON response dict.

    Raises:
        SuperGETError: On network errors, timeouts, or invalid responses.
    """
    settings = get_settings()
    if not settings.superget_api_key:
        raise SuperGETError(
            message_he="מפתח API של SuperGET לא הוגדר",
            message_en="SuperGET API key not configured",
        )

    payload: dict[str, object] = {
        "action": action,
        "api_key": settings.superget_api_key,
    }
    if params:
        payload.update(params)

    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 2):
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(SUPERGET_BASE_URL, json=payload)
                response.raise_for_status()

                data: dict[str, object] = response.json()

                # SuperGET returns status field to indicate success/failure
                if data.get("status") == "error":
                    error_msg = str(data.get("message", "Unknown SuperGET error"))
                    raise SuperGETError(
                        message_he="שגיאה מ-SuperGET",
                        message_en=f"SuperGET API error: {error_msg}",
                        details={"action": action, "response": data},
                    )

                await logger.ainfo(
                    "superget_request_success",
                    action=action,
                    attempt=attempt,
                )
                return data

        except SuperGETError:
            raise
        except httpx.HTTPStatusError as exc:
            last_error = exc
            await logger.awarning(
                "superget_http_error",
                action=action,
                attempt=attempt,
                status_code=exc.response.status_code,
                error=str(exc),
            )
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            last_error = exc
            await logger.awarning(
                "superget_request_error",
                action=action,
                attempt=attempt,
                error=str(exc),
                error_type=type(exc).__name__,
            )
        except Exception as exc:
            last_error = exc
            await logger.aerror(
                "superget_unexpected_error",
                action=action,
                attempt=attempt,
                error=str(exc),
                error_type=type(exc).__name__,
            )

        if attempt >= MAX_RETRIES + 1:
            break

    raise SuperGETError(
        message_he="שגיאה בתקשורת עם SuperGET לאחר מספר ניסיונות",
        message_en=f"SuperGET API failed after {MAX_RETRIES + 1} attempts",
        details={"action": action, "last_error": str(last_error)},
    )


def _parse_store_prices(
    data: dict[str, object],
    product_name: str,
    barcode: str | None = None,
) -> list[StorePrice]:
    """Parse SuperGET response into StorePrice list.

    Handles multiple response formats — the API may return results
    under 'data', 'results', or 'items' keys.
    """
    results: list[StorePrice] = []

    # Try common response structures
    raw_items = data.get("data") or data.get("results") or data.get("items")
    if not isinstance(raw_items, list):
        return results

    for item in raw_items:
        if not isinstance(item, dict):
            continue

        price = _safe_decimal(item.get("price") or item.get("item_price"))
        if price is None or price <= 0:
            continue

        store_name = str(item.get("chain_name") or item.get("store_name") or "")
        if not store_name:
            continue

        results.append(
            StorePrice(
                store_name=store_name,
                store_branch=str(item["branch_name"]) if item.get("branch_name") else None,
                price=price,
                product_name=str(item.get("item_name", product_name)),
                barcode=str(item.get("barcode", barcode or "")),
            )
        )

    return results


async def search_product_by_barcode(barcode: str) -> list[StorePrice]:
    """Search SuperGET for a product by barcode.

    Returns a list of prices across different stores.
    """
    data = await _superget_request(
        "SearchByBarcode",
        {"barcode": barcode},
    )
    return _parse_store_prices(data, product_name="", barcode=barcode)


async def search_product_by_name(name: str) -> list[StorePrice]:
    """Search SuperGET for a product by name.

    Returns a list of prices across different stores.
    """
    data = await _superget_request(
        "SearchProduct",
        {"product_name": name},
    )
    return _parse_store_prices(data, product_name=name)


async def get_prices_for_product(
    product: Product,
) -> list[StorePrice]:
    """Get prices for a product using barcode first, then name fallback.

    Priority:
    1. Barcode search (exact match)
    2. Name search (may return multiple products — caller filters)
    """
    # 1. Try barcode first
    if product.barcode:
        try:
            prices = await search_product_by_barcode(product.barcode)
            if prices:
                await logger.ainfo(
                    "price_found_by_barcode",
                    product_id=str(product.id),
                    barcode=product.barcode,
                    price_count=len(prices),
                )
                return prices
        except SuperGETError:
            await logger.awarning(
                "barcode_search_failed_trying_name",
                product_id=str(product.id),
                barcode=product.barcode,
            )

    # 2. Fall back to name search
    try:
        prices = await search_product_by_name(product.name)
        if prices:
            await logger.ainfo(
                "price_found_by_name",
                product_id=str(product.id),
                name=product.name,
                price_count=len(prices),
            )
        return prices
    except SuperGETError:
        await logger.awarning(
            "name_search_failed",
            product_id=str(product.id),
            name=product.name,
        )
        return []


async def save_prices_to_history(
    db: AsyncSession,
    product_id: uuid.UUID,
    prices: list[StorePrice],
) -> int:
    """Save SuperGET price results to PriceHistory table.

    Returns the number of price records saved.
    """
    now = datetime.now(timezone.utc)
    saved_count = 0

    for sp in prices:
        # Check for existing price record from today for same product/store
        existing = await db.execute(
            select(PriceHistory).where(
                PriceHistory.product_id == product_id,
                PriceHistory.store_name == sp.store_name,
                PriceHistory.source == "superget",
            ).order_by(PriceHistory.observed_at.desc()).limit(1)
        )
        existing_record = existing.scalar_one_or_none()

        # Skip if we already have a recent price (within 24 hours) for this store
        if existing_record and (now - existing_record.observed_at).total_seconds() < 86400:
            continue

        record = PriceHistory(
            product_id=product_id,
            store_name=sp.store_name,
            store_branch=sp.store_branch,
            price=sp.price,
            source="superget",
            observed_at=now,
        )
        db.add(record)
        saved_count += 1

    if saved_count > 0:
        await db.flush()
        await logger.ainfo(
            "prices_saved_to_history",
            product_id=str(product_id),
            saved_count=saved_count,
        )

    return saved_count


async def fetch_and_save_prices(
    db: AsyncSession,
    product: Product,
) -> ProductPriceResult:
    """Fetch prices from SuperGET for a product and save to history.

    This is the main entry point: fetches prices, saves them, and returns the result.
    Gracefully returns empty result on API failure (no exception raised to caller).
    """
    result = ProductPriceResult(
        product_id=product.id,
        product_name=product.name,
    )

    try:
        prices = await get_prices_for_product(product)
    except SuperGETError as exc:
        await logger.awarning(
            "price_fetch_failed",
            product_id=str(product.id),
            error=str(exc),
        )
        return result

    if not prices:
        return result

    result.prices = prices
    result.matched = True

    await save_prices_to_history(db, product.id, prices)

    return result


async def fetch_prices_for_products(
    db: AsyncSession,
    product_ids: list[uuid.UUID],
) -> list[ProductPriceResult]:
    """Fetch prices for multiple products from SuperGET.

    Loads products from DB, queries SuperGET for each, and saves results.
    Returns list of price results (one per product).
    """
    results: list[ProductPriceResult] = []

    for pid in product_ids:
        product_result = await db.execute(
            select(Product).where(Product.id == pid)
        )
        product = product_result.scalar_one_or_none()
        if product is None:
            continue

        price_result = await fetch_and_save_prices(db, product)
        results.append(price_result)

    return results


async def save_receipt_prices_to_history(
    db: AsyncSession,
    purchases: list,
    store_name: str | None,
    store_branch: str | None = None,
    receipt_date: datetime | None = None,
) -> int:
    """Save prices from a parsed receipt to PriceHistory.

    Extracts unit_price from each matched purchase and writes to PriceHistory
    with source='receipt'. This allows price comparison to work from receipt
    data alone, without needing the SuperGET API.

    Returns the number of price records saved.
    """
    if not store_name:
        return 0

    observed_at = receipt_date or datetime.now(timezone.utc)
    saved_count = 0

    for purchase in purchases:
        if not purchase.product_id or not purchase.unit_price:
            continue

        record = PriceHistory(
            product_id=purchase.product_id,
            store_name=store_name,
            store_branch=store_branch,
            price=purchase.unit_price,
            source="receipt",
            observed_at=observed_at,
        )
        db.add(record)
        saved_count += 1

    if saved_count > 0:
        await db.flush()
        await logger.ainfo(
            "receipt_prices_saved_to_history",
            store=store_name,
            saved_count=saved_count,
        )

    return saved_count
