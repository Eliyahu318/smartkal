from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.list_item import ListItem
    from app.models.product import Product
    from app.models.user import User


class ListItemAlias(UUIDMixin, TimestampMixin, Base):
    """Per-user mapping from a global Product to a user's ListItem.

    This lets multiple SKU-level products (e.g. "עגבניות שרי", "עגבניות שרי פרימיום",
    "עגבניות שרי עגול") all feed the same ListItem on a single user's shopping list,
    without merging them at the global Product level (which would corrupt cross-user
    PriceHistory). The (user_id, product_id) pair is unique — a product can map to at
    most one list item per user.
    """

    __tablename__ = "list_item_aliases"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "product_id", name="uq_list_item_aliases_user_product"
        ),
        Index("ix_list_item_aliases_list_item", "list_item_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    list_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("list_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )

    user: Mapped[User] = relationship()
    list_item: Mapped[ListItem] = relationship(back_populates="aliases")
    product: Mapped[Product] = relationship(back_populates="list_item_aliases")
