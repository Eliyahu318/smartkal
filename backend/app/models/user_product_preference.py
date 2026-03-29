from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.user import User


class UserProductPreference(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "user_product_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_user_product_pref"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    custom_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    preferred_store: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auto_refresh_days: Mapped[int | None] = mapped_column(nullable=True)
    is_favorite: Mapped[bool] = mapped_column(server_default=text("false"), nullable=False)

    user: Mapped[User] = relationship(back_populates="preferences")
    product: Mapped[Product] = relationship(back_populates="preferences")
