"""add order status_updated_at

Revision ID: f4a5b6c7d8e9
Revises: f6ebb7c00db6
Create Date: 2026-06-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f4a5b6c7d8e9"
down_revision: str | None = "f6ebb7c00db6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Backfill existing rows with now() via the server_default, then keep the
    # default so the column is always populated even if a path forgets to set it.
    op.add_column(
        "orders_orders",
        sa.Column(
            "status_updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_column("orders_orders", "status_updated_at")
