"""drop products.category_id

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-09 12:00:00.000000

Removes the per-user `category_id` field from the global `products` table.

Why: `Product` is shared across users (used by PriceHistory for cross-user
price comparison) but `category_id` references `categories.id` which is
per-user (Category.user_id). The first user to upload a receipt for a given
product would "win" — their category_id would be cached on the global
Product, and every subsequent user would inherit a category_id pointing to
a category they don't own. The frontend then rendered those items as
"ללא קטגוריה" because the cat_id was missing from the user's category map.

After this migration, categorization happens at receipt-parse time
(Claude returns a category NAME per item) and is resolved per-user via
`Category WHERE user_id=? AND name=?` at insert time. There is no shared
place to store a category_id on a global entity, so cross-user pollution
is structurally impossible.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the FK constraint first, then the column
    op.drop_constraint(
        "products_category_id_fkey", "products", type_="foreignkey"
    )
    op.drop_column("products", "category_id")


def downgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "products_category_id_fkey",
        "products",
        "categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )
