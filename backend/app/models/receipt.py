from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.user import User


class Receipt(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "receipts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    store_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    store_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    receipt_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    pdf_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), server_default=text("'pending'"), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="receipts")
    purchases: Mapped[list[Purchase]] = relationship(
        back_populates="receipt", cascade="all, delete-orphan"
    )


class Purchase(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "purchases"

    receipt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    raw_name: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[float | None] = mapped_column(nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    total_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(50), nullable=True)
    matched: Mapped[bool] = mapped_column(server_default=text("false"), nullable=False)

    receipt: Mapped[Receipt] = relationship(back_populates="purchases")
    product: Mapped[Product | None] = relationship(back_populates="purchases")
