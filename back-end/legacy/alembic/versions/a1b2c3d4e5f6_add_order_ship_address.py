"""add order ship address snapshot

Revision ID: a1b2c3d4e5f6
Revises: f4a5b6c7d8e9
Create Date: 2026-06-14 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f4a5b6c7d8e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = (
    ("ship_label", 60),
    ("ship_zip_code", 9),
    ("ship_street", 160),
    ("ship_number", 20),
    ("ship_complement", 120),
    ("ship_neighborhood", 120),
    ("ship_city", 120),
    ("ship_state", 2),
)


def upgrade() -> None:
    for name, length in _COLUMNS:
        op.add_column("orders_orders", sa.Column(name, sa.String(length=length), nullable=True))


def downgrade() -> None:
    for name, _ in reversed(_COLUMNS):
        op.drop_column("orders_orders", name)
