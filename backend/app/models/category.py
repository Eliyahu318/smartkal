from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.list_item import ListItem
    from app.models.product import Product
    from app.models.user import User


class Category(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_category_user_name"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    display_order: Mapped[int] = mapped_column(server_default=text("0"), nullable=False)
    is_default: Mapped[bool] = mapped_column(server_default=text("false"), nullable=False)

    user: Mapped[User] = relationship(back_populates="categories")
    products: Mapped[list[Product]] = relationship(back_populates="category")
    list_items: Mapped[list[ListItem]] = relationship(back_populates="category")
