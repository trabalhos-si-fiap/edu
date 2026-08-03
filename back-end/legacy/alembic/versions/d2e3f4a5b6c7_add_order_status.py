"""add order status

Revision ID: d2e3f4a5b6c7
Revises: c1a2b3d4e5f6
Create Date: 2026-06-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d2e3f4a5b6c7"
down_revision: str | None = "c1a2b3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orders_orders",
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
    )
    op.create_check_constraint(
        "ck_orders_orders_status",
        "orders_orders",
        "status IN ('pending', 'confirmed', 'separating', 'out_for_delivery', 'delivered')",
    )
    # Drop the server_default now that existing rows are backfilled; the
    # application sets the initial value explicitly.
    op.alter_column("orders_orders", "status", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_orders_orders_status", "orders_orders", type_="check")
    op.drop_column("orders_orders", "status")
