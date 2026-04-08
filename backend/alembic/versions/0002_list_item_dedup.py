"""list item dedup: canonical_key, aliases, merge log

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-08 12:00:00.000000

Adds the per-user list-item dedup machinery:
- products.canonical_name: short variant-free name (filled by Claude or by canonicalizer)
- list_items.canonical_key: per-user normalized canonical name used to detect duplicates
- list_item_aliases: maps (user, product) -> list_item, so multiple SKU products can
  feed the same list item without polluting the global products table
- list_item_merge_log: append-only audit of every merge, with full source snapshot
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- products.canonical_name ---
    op.add_column(
        "products",
        sa.Column("canonical_name", sa.String(500), nullable=True),
    )
    op.create_index(
        "ix_products_canonical_name",
        "products",
        ["canonical_name"],
    )

    # --- list_items.canonical_key ---
    op.add_column(
        "list_items",
        sa.Column("canonical_key", sa.String(500), nullable=True),
    )
    op.create_index(
        "ix_list_items_user_canonical",
        "list_items",
        ["user_id", "canonical_key"],
    )
    # Note: we intentionally DO NOT add a unique constraint on
    # (user_id, canonical_key). The dedup feature *requires* multiple list
    # items to share the same canonical_key during the detection window so
    # find_duplicate_groups can surface them. The "at most one list item per
    # canonical" invariant for new purchases is enforced in application code
    # via resolve_list_item_target() (which finds the existing item via the
    # canonical_key index and reuses it instead of creating a new one).

    # --- list_item_aliases ---
    op.create_table(
        "list_item_aliases",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "list_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("list_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id",
            "product_id",
            name="uq_list_item_aliases_user_product",
        ),
    )
    op.create_index(
        "ix_list_item_aliases_list_item",
        "list_item_aliases",
        ["list_item_id"],
    )

    # --- list_item_merge_log (append-only audit) ---
    op.create_table(
        "list_item_merge_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # source_id is intentionally NOT a FK — the source row is deleted
        # by the merge operation and we still want the audit row to survive.
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_name", sa.String(500), nullable=False),
        sa.Column("source_payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "target_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("list_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "merged_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_list_item_merge_log_user_merged_at",
        "list_item_merge_log",
        ["user_id", "merged_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_list_item_merge_log_user_merged_at",
        table_name="list_item_merge_log",
    )
    op.drop_table("list_item_merge_log")

    op.drop_index(
        "ix_list_item_aliases_list_item",
        table_name="list_item_aliases",
    )
    op.drop_table("list_item_aliases")

    op.drop_index("ix_list_items_user_canonical", table_name="list_items")
    op.drop_column("list_items", "canonical_key")

    op.drop_index("ix_products_canonical_name", table_name="products")
    op.drop_column("products", "canonical_name")
