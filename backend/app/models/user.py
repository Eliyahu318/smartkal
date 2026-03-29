from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.list_item import ListItem
    from app.models.receipt import Receipt
    from app.models.user_product_preference import UserProductPreference


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    picture_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    google_sub: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(server_default=text("true"), nullable=False)

    categories: Mapped[list[Category]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    list_items: Mapped[list[ListItem]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    receipts: Mapped[list[Receipt]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    preferences: Mapped[list[UserProductPreference]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
