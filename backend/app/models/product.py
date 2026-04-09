from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.list_item import ListItem
    from app.models.list_item_alias import ListItemAlias
    from app.models.price_history import PriceHistory
    from app.models.receipt import Purchase
    from app.models.user_product_preference import UserProductPreference


class Product(UUIDMixin, TimestampMixin, Base):
    """A globally-shared product identity (name + barcode + canonical form).

    Intentionally has NO category — categorization is a per-user concept and
    must live on `ListItem.category_id`, never on Product. See migration
    0003_drop_product_category_id for the rationale.
    """

    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_normalized_name", "normalized_name"),
        Index("ix_products_barcode", "barcode"),
        Index("ix_products_canonical_name", "canonical_name"),
    )

    name: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(500), nullable=False)
    canonical_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(50), nullable=True)

    list_items: Mapped[list[ListItem]] = relationship(back_populates="product")
    purchases: Mapped[list[Purchase]] = relationship(back_populates="product")
    price_history: Mapped[list[PriceHistory]] = relationship(back_populates="product")
    preferences: Mapped[list[UserProductPreference]] = relationship(back_populates="product")
    list_item_aliases: Mapped[list[ListItemAlias]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
