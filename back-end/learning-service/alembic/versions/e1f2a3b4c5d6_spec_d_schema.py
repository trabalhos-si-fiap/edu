"""spec D schema: objetivo do aluno, etapas do roadmap, extrato de pontos

Revision ID: e1f2a3b4c5d6
Revises: b9e63fa43f39
Create Date: 2026-09-10

Aditiva: só cria tabelas novas. Nenhuma coluna existente muda, então o
`downgrade` é o inverso exato e não perde dado de nada que já existia.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: str | Sequence[str] | None = "b9e63fa43f39"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "objetivo_aluno",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("aluno_id", UUID(as_uuid=True), nullable=False),
        sa.Column("titulo", sa.String(length=120), nullable=False),
        sa.Column("data_alvo", sa.Date(), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("aluno_id", name="uq_objetivo_aluno"),
    )
    op.create_index("ix_objetivo_aluno_aluno_id", "objetivo_aluno", ["aluno_id"])

    op.create_table(
        "etapa_roadmap",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("aluno_id", UUID(as_uuid=True), nullable=False),
        sa.Column("subtema_id", sa.Integer(), sa.ForeignKey("subtema.id"), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("prazo", sa.Date(), nullable=False),
        sa.Column("concluida_em", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("aluno_id", "subtema_id", name="uq_etapa_aluno_subtema"),
    )
    op.create_index("ix_etapa_roadmap_aluno_id", "etapa_roadmap", ["aluno_id"])

    op.create_table(
        "lancamento_pontos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("aluno_id", UUID(as_uuid=True), nullable=False),
        sa.Column("origem", sa.String(length=20), nullable=False),
        sa.Column("referencia", sa.String(length=60), nullable=False),
        sa.Column("pontos", sa.Integer(), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("aluno_id", "origem", "referencia", name="uq_lancamento_idempotente"),
    )
    op.create_index("ix_lancamento_pontos_aluno_id", "lancamento_pontos", ["aluno_id"])


def downgrade() -> None:
    op.drop_index("ix_lancamento_pontos_aluno_id", table_name="lancamento_pontos")
    op.drop_table("lancamento_pontos")
    op.drop_index("ix_etapa_roadmap_aluno_id", table_name="etapa_roadmap")
    op.drop_table("etapa_roadmap")
    op.drop_index("ix_objetivo_aluno_aluno_id", table_name="objetivo_aluno")
    op.drop_table("objetivo_aluno")
