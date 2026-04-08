from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.list_item_alias import ListItemAlias
    from app.models.product import Product
    from app.models.user import User


class ListItemStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"


class ListItemSource(str, enum.Enum):
    MANUAL = "manual"
    RECEIPT = "receipt"
    AUTO_REFRESH = "auto_refresh"


class ListItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "list_items"
    __table_args__ = (
        Index("ix_list_items_user_status", "user_id", "status"),
        Index("ix_list_items_refresh", "status", "next_refresh_at"),
        Index("ix_list_items_user_canonical", "user_id", "canonical_key"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    canonical_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    quantity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), server_default=text("'active'"), nullable=False
    )
    last_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    auto_refresh_days: Mapped[int | None] = mapped_column(nullable=True)
    system_refresh_days: Mapped[int | None] = mapped_column(nullable=True)
    next_refresh_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source: Mapped[str] = mapped_column(
        String(20), server_default=text("'manual'"), nullable=False
    )
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    display_order: Mapped[int] = mapped_column(server_default=text("0"), nullable=False)

    user: Mapped[User] = relationship(back_populates="list_items")
    product: Mapped[Product | None] = relationship(back_populates="list_items")
    category: Mapped[Category | None] = relationship(back_populates="list_items")
    aliases: Mapped[list[ListItemAlias]] = relationship(
        back_populates="list_item", cascade="all, delete-orphan"
    )
