"""spec C schema: carregamentos, posicao_entrega, order shipment and destination

Revision ID: c1d2e3f4a5b6
Revises: b1a2c3d4e5f6
Create Date: 2026-09-09

Aditiva: duas tabelas novas e três colunas nulas em `orders`. Nenhum backfill,
nenhuma coluna existente muda de tipo ou de nulidade — o banco de
desenvolvimento do usuário sobrevive a ela sem tocar em dado nenhum.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: str | Sequence[str] | None = "b1a2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "carregamentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "transportadora_id",
            sa.Integer(),
            sa.ForeignKey("carriers.id"),
            nullable=False,
        ),
        sa.Column("origem_rotulo", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("origem_lat", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("origem_lng", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("codigo", sa.String(length=12), nullable=False),
        sa.Column("senha_hash", sa.String(length=255), nullable=False),
        sa.Column("entregador_nome", sa.String(length=120), nullable=True),
        sa.Column("entregador_contato", sa.String(length=120), nullable=True),
        sa.Column("aberto_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("criado_por", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_carregamentos_codigo", "carregamentos", ["codigo"], unique=True)
    op.create_index("ix_carregamentos_transportadora_id", "carregamentos", ["transportadora_id"])

    op.create_table(
        "posicao_entrega",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "carregamento_id",
            sa.Integer(),
            sa.ForeignKey("carregamentos.id"),
            nullable=False,
        ),
        sa.Column("lat", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("lng", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column(
            "registrado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_posicao_entrega_carregamento_id", "posicao_entrega", ["carregamento_id"])
    op.create_index("ix_posicao_entrega_registrado_em", "posicao_entrega", ["registrado_em"])

    op.add_column("orders", sa.Column("carregamento_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_orders_carregamento_id", "orders", "carregamentos", ["carregamento_id"], ["id"]
    )
    op.create_index("ix_orders_carregamento_id", "orders", ["carregamento_id"])
    op.add_column(
        "orders", sa.Column("destino_lat", sa.Numeric(precision=9, scale=6), nullable=True)
    )
    op.add_column(
        "orders", sa.Column("destino_lng", sa.Numeric(precision=9, scale=6), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("orders", "destino_lng")
    op.drop_column("orders", "destino_lat")
    op.drop_index("ix_orders_carregamento_id", table_name="orders")
    op.drop_constraint("fk_orders_carregamento_id", "orders", type_="foreignkey")
    op.drop_column("orders", "carregamento_id")
    op.drop_index("ix_posicao_entrega_registrado_em", table_name="posicao_entrega")
    op.drop_index("ix_posicao_entrega_carregamento_id", table_name="posicao_entrega")
    op.drop_table("posicao_entrega")
    op.drop_index("ix_carregamentos_transportadora_id", table_name="carregamentos")
    op.drop_index("ix_carregamentos_codigo", table_name="carregamentos")
    op.drop_table("carregamentos")
