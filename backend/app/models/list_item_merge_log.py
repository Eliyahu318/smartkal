from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.list_item import ListItem
    from app.models.user import User


class ListItemMergeLog(UUIDMixin, Base):
    """Append-only audit log for every list-item merge operation.

    Stores a complete JSON snapshot of the source list item before it is deleted,
    so support requests like "where did my item go?" can be answered, and a future
    undo feature can reconstruct the deleted row. Intentionally has no updated_at:
    rows here are immutable history.
    """

    __tablename__ = "list_item_merge_log"
    __table_args__ = (
        Index("ix_list_item_merge_log_user_merged_at", "user_id", "merged_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Not a FK — the source ListItem row is deleted by the merge operation,
    # and we still want this audit row to survive.
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_name: Mapped[str] = mapped_column(String(500), nullable=False)
    source_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("list_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    merged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship()
    target: Mapped[ListItem | None] = relationship()
