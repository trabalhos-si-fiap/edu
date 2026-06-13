"""add user is_admin

Revision ID: f6ebb7c00db6
Revises: f4a5b6c7d8e9
Create Date: 2026-06-13 19:16:55.940112

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f6ebb7c00db6"
down_revision: str | None = "e3f4a5b6c7d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "auth_users",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("auth_users", "is_admin")
