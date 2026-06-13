"""update education_level check constraint to grade-based values

Revision ID: c1a2b3d4e5f6
Revises: 60934c36c65d
Create Date: 2026-06-13 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "c1a2b3d4e5f6"
down_revision: str | None = "60934c36c65d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT = "ck_auth_users_education_level"
_NEW_VALUES = "'9º ano','1º ano','2º ano','3º ano','Vestibulando'"
_OLD_VALUES = (
    "'Ensino Fundamental','Ensino Médio','Ensino Superior','Pós-graduação','Mestrado','Doutorado'"
)


def upgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "auth_users", type_="check")
    op.create_check_constraint(
        _CONSTRAINT,
        "auth_users",
        f"education_level IN ({_NEW_VALUES})",
    )


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "auth_users", type_="check")
    op.create_check_constraint(
        _CONSTRAINT,
        "auth_users",
        f"education_level IN ({_OLD_VALUES})",
    )
