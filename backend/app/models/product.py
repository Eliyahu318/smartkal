from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.list_item import ListItem
    from app.models.price_history import PriceHistory
    from app.models.receipt import Purchase
    from app.models.user_product_preference import UserProductPreference


class Product(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_normalized_name", "normalized_name"),
        Index("ix_products_barcode", "barcode"),
    )

    name: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(500), nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )

    category: Mapped[Category | None] = relationship(back_populates="products")
    list_items: Mapped[list[ListItem]] = relationship(back_populates="product")
    purchases: Mapped[list[Purchase]] = relationship(back_populates="product")
    price_history: Mapped[list[PriceHistory]] = relationship(back_populates="product")
    preferences: Mapped[list[UserProductPreference]] = relationship(back_populates="product")
