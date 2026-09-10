"""staff registry

Revision ID: d4c5b6a7e8f9
Revises: 886205d547cc
Create Date: 2026-09-09 00:00:00.000000

Task 8 da spec C (D6 do plano): o notification-service precisa saber "quem é
staff" para endereçar um push por transição de pedido (admin, separador,
entregador). Consultar o auth-users em runtime exigiria este serviço
fabricar um token de admin para si mesmo — um serviço que não é dono de
identidade emitindo credencial de identidade — e o payload do commerce não
resolveria `order.created`, que precisa avisar gente que ainda não tocou no
pedido. A tabela é uma réplica local, alimentada pelo evento `staff.created`
que `auth-users-service` já publica.

`user_id` é a PK (o id vem do auth-users, único lá) — não precisa de índice
próprio. `papel` ganha índice porque é o filtro de toda leitura
(`destinatarios.resolver` faz `WHERE papel IN (...)`).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4c5b6a7e8f9"
down_revision: str | Sequence[str] | None = "886205d547cc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "staff",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("papel", sa.String(length=20), nullable=False),
        sa.Column("nome", sa.String(length=150), server_default="", nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index(op.f("ix_staff_papel"), "staff", ["papel"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_staff_papel"), table_name="staff")
    op.drop_table("staff")
