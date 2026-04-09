"""Receipt API endpoints: upload PDF, view receipt, list receipts."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.errors import NotFoundError, ValidationError
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.receipt import Purchase, Receipt
from app.models.user import User
from app.services.price_comparator import fetch_prices_for_products, save_receipt_prices_to_history
from app.services.product_matcher import match_receipt_purchases
from app.services.receipt_parser import ParsedReceipt, parse_receipt
from app.utils.pdf import extract_text_from_pdf

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

router = APIRouter(prefix="/receipts", tags=["receipts"])

# PDF magic bytes: %PDF
_PDF_MAGIC = b"%PDF"
_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# --- Request / Response schemas ---


class PurchaseResponse(BaseModel):
    id: uuid.UUID
    raw_name: str
    quantity: float | None
    unit_price: Decimal | None
    total_price: Decimal | None
    barcode: str | None
    matched: bool
    product_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReceiptResponse(BaseModel):
    id: uuid.UUID
    store_name: str | None
    store_branch: str | None
    receipt_date: date | None
    total_amount: Decimal | None
    pdf_filename: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReceiptDetailResponse(ReceiptResponse):
    purchases: list[PurchaseResponse]


class ReceiptListResponse(BaseModel):
    receipts: list[ReceiptResponse]
    total: int
    page: int
    page_size: int


class MatchCountsResponse(BaseModel):
    barcode: int = 0
    exact_name: int = 0
    fuzzy: int = 0
    new: int = 0
    completed_items: int = 0
    auto_merged_to_existing: int = 0
    completed_via_alias: int = 0


class UploadReceiptResponse(BaseModel):
    receipt: ReceiptDetailResponse
    parsed_item_count: int
    match_counts: MatchCountsResponse | None = None


# --- Helpers ---


def _validate_pdf(content: bytes, filename: str | None) -> None:
    """Validate that the uploaded file is a PDF within size limits."""
    if len(content) > _MAX_FILE_SIZE:
        raise ValidationError(
            message_he="הקובץ גדול מדי — מקסימום 10MB",
            message_en="File too large — maximum 10MB",
            details={"max_bytes": _MAX_FILE_SIZE, "actual_bytes": len(content)},
        )

    if not content[:4].startswith(_PDF_MAGIC):
        raise ValidationError(
            message_he="הקובץ אינו PDF תקין",
            message_en="File is not a valid PDF",
            details={"filename": filename},
        )


def _build_purchases_from_parsed(
    receipt_id: uuid.UUID,
    parsed: ParsedReceipt,
) -> list[Purchase]:
    """Create Purchase ORM objects from parsed receipt data."""
    purchases: list[Purchase] = []
    for item in parsed.items:
        purchase = Purchase(
            receipt_id=receipt_id,
            raw_name=item.name,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_price=item.total_price,
            barcode=item.barcode,
            matched=False,
        )
        purchases.append(purchase)
    return purchases


# --- Endpoints ---


@router.post("/upload", response_model=UploadReceiptResponse, status_code=201)
async def upload_receipt(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Upload a receipt PDF, extract text, parse with Claude, save results.

    Validates the file (PDF magic bytes, max 10MB), extracts text via PyMuPDF,
    parses with Claude AI, and saves Receipt + Purchase records.
    """
    content = await file.read()

    _validate_pdf(content, file.filename)

    # Extract text from PDF
    raw_text = extract_text_from_pdf(content)

    # Parse with Claude AI
    parsed = await parse_receipt(raw_text)

    # Parse receipt_date string to date object
    receipt_date_obj: date | None = None
    if parsed.receipt_date:
        try:
            receipt_date_obj = date.fromisoformat(parsed.receipt_date)
        except ValueError:
            receipt_date_obj = None

    # Create Receipt record
    receipt = Receipt(
        user_id=current_user.id,
        store_name=parsed.store_name,
        store_branch=parsed.store_branch,
        receipt_date=receipt_date_obj,
        total_amount=parsed.total_amount,
        raw_text=raw_text,
        parsed_json=parsed.raw_json,
        pdf_filename=file.filename,
        status="parsed",
    )
    db.add(receipt)
    await db.flush()

    # Create Purchase records
    purchases = _build_purchases_from_parsed(receipt.id, parsed)
    for purchase in purchases:
        db.add(purchase)
    await db.flush()

    # Parallel hints from the parser (same order as `purchases`):
    # - canonicals: per-user dedup layer (canonical_key on ListItem)
    # - categories: per-user category resolution by NAME (no global cache)
    canonicals = [item.canonical_name for item in parsed.items]
    categories_hint = [item.category_name for item in parsed.items]

    # Match purchases to products, complete matching list items
    match_counts = await match_receipt_purchases(
        db,
        receipt,
        current_user.id,
        purchases,
        canonicals=canonicals,
        categories=categories_hint,
    )

    # Save receipt prices to PriceHistory for comparison
    await save_receipt_prices_to_history(
        db, purchases, receipt.store_name, receipt.store_branch,
    )

    # Best-effort: fetch prices from SuperGET for matched products
    settings = get_settings()
    if settings.superget_api_key:
        product_ids = [p.product_id for p in purchases if p.product_id]
        if product_ids:
            try:
                await fetch_prices_for_products(db, product_ids)
            except Exception as exc:
                await logger.awarning(
                    "price_fetch_after_receipt_failed",
                    receipt_id=str(receipt.id),
                    error=str(exc),
                )

    await logger.ainfo(
        "receipt_uploaded",
        receipt_id=str(receipt.id),
        store=parsed.store_name,
        item_count=len(purchases),
        total=str(parsed.total_amount),
        match_counts=match_counts,
    )

    detail = ReceiptDetailResponse(
        id=receipt.id,
        store_name=receipt.store_name,
        store_branch=receipt.store_branch,
        receipt_date=receipt.receipt_date,
        total_amount=receipt.total_amount,
        pdf_filename=receipt.pdf_filename,
        status=receipt.status,
        created_at=receipt.created_at,
        updated_at=receipt.updated_at,
        purchases=[PurchaseResponse.model_validate(p) for p in purchases],
    )

    return UploadReceiptResponse(
        receipt=detail,
        parsed_item_count=len(purchases),
        match_counts=MatchCountsResponse(**match_counts),
    )


@router.get("/{receipt_id}", response_model=ReceiptDetailResponse)
async def get_receipt(
    receipt_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Return a full receipt with its parsed items."""
    result = await db.execute(
        select(Receipt)
        .options(selectinload(Receipt.purchases))
        .where(
            Receipt.id == receipt_id,
            Receipt.user_id == current_user.id,
        )
    )
    receipt = result.scalar_one_or_none()

    if receipt is None:
        raise NotFoundError(
            message_he="הקבלה לא נמצאה",
            message_en="Receipt not found",
        )

    return ReceiptDetailResponse(
        id=receipt.id,
        store_name=receipt.store_name,
        store_branch=receipt.store_branch,
        receipt_date=receipt.receipt_date,
        total_amount=receipt.total_amount,
        pdf_filename=receipt.pdf_filename,
        status=receipt.status,
        created_at=receipt.created_at,
        updated_at=receipt.updated_at,
        purchases=[PurchaseResponse.model_validate(p) for p in receipt.purchases],
    )


@router.post("/{receipt_id}/reprocess", response_model=UploadReceiptResponse)
async def reprocess_receipt(
    receipt_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Reprocess an existing receipt: re-run product matching and create list items.

    Useful for receipts uploaded before list-item creation was implemented.
    Does NOT re-parse the PDF or change timestamps.
    """
    result = await db.execute(
        select(Receipt)
        .options(selectinload(Receipt.purchases))
        .where(
            Receipt.id == receipt_id,
            Receipt.user_id == current_user.id,
        )
    )
    receipt = result.scalar_one_or_none()

    if receipt is None:
        raise NotFoundError(
            message_he="הקבלה לא נמצאה",
            message_en="Receipt not found",
        )

    purchases = list(receipt.purchases)

    # Try to recover canonical_name + category hints from the stored parser
    # JSON. If the receipt was uploaded before the parser started emitting
    # these fields, the corresponding entries will be None — the matcher will
    # fall back to the deterministic canonicalizer / per-user auto_categorize.
    canonicals: list[str | None] | None = None
    categories_hint: list[str | None] | None = None
    parsed_json = receipt.parsed_json
    if isinstance(parsed_json, dict):
        items_payload = parsed_json.get("items")
        if isinstance(items_payload, list) and len(items_payload) == len(purchases):
            recovered_canon: list[str | None] = []
            recovered_cats: list[str | None] = []
            for item in items_payload:
                if isinstance(item, dict):
                    cn = item.get("canonical_name")
                    recovered_canon.append(
                        cn.strip() if isinstance(cn, str) and cn.strip() else None
                    )
                    cat = item.get("category")
                    recovered_cats.append(
                        cat.strip() if isinstance(cat, str) and cat.strip() else None
                    )
                else:
                    recovered_canon.append(None)
                    recovered_cats.append(None)
            canonicals = recovered_canon
            categories_hint = recovered_cats

    match_counts = await match_receipt_purchases(
        db,
        receipt,
        current_user.id,
        purchases,
        canonicals=canonicals,
        categories=categories_hint,
    )

    # Save receipt prices to PriceHistory for comparison
    await save_receipt_prices_to_history(
        db, purchases, receipt.store_name, receipt.store_branch,
    )

    # Best-effort: fetch prices from SuperGET for matched products
    settings = get_settings()
    if settings.superget_api_key:
        product_ids = [p.product_id for p in purchases if p.product_id]
        if product_ids:
            try:
                await fetch_prices_for_products(db, product_ids)
            except Exception as exc:
                await logger.awarning(
                    "price_fetch_after_reprocess_failed",
                    receipt_id=str(receipt.id),
                    error=str(exc),
                )

    await db.commit()

    await logger.ainfo(
        "receipt_reprocessed",
        receipt_id=str(receipt.id),
        match_counts=match_counts,
    )

    detail = ReceiptDetailResponse(
        id=receipt.id,
        store_name=receipt.store_name,
        store_branch=receipt.store_branch,
        receipt_date=receipt.receipt_date,
        total_amount=receipt.total_amount,
        pdf_filename=receipt.pdf_filename,
        status=receipt.status,
        created_at=receipt.created_at,
        updated_at=receipt.updated_at,
        purchases=[PurchaseResponse.model_validate(p) for p in purchases],
    )

    return UploadReceiptResponse(
        receipt=detail,
        parsed_item_count=len(purchases),
        match_counts=MatchCountsResponse(**match_counts),
    )


@router.get("", response_model=ReceiptListResponse)
async def list_receipts(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Return a paginated list of all receipts for the current user."""
    # Count total
    count_result = await db.execute(
        select(func.count()).select_from(Receipt).where(
            Receipt.user_id == current_user.id,
        )
    )
    total = count_result.scalar_one()

    # Fetch page
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Receipt)
        .where(Receipt.user_id == current_user.id)
        .order_by(Receipt.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    receipts = list(result.scalars().all())

    return ReceiptListResponse(
        receipts=[ReceiptResponse.model_validate(r) for r in receipts],
        total=total,
        page=page,
        page_size=page_size,
    )
