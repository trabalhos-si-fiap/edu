"""spec B: partner origin, stock audit, carriers, order origin

Revision ID: b1a2c3d4e5f6
Revises: c90210e9965c
Create Date: 2026-09-08

ADITIVA POR CONSTRUÇÃO, e é isso que a distingue de três vizinhas desta
cadeia. `1308bb221890`, `bd410bba0e85` e `099099b0c1a8` são reconstruções:
elas apagam dado de propósito, e por isso o `downgrade()` das três levanta
`RuntimeError` incondicional. Esta não apaga nada — só acrescenta colunas com
`server_default` e cria duas tabelas —, então o `downgrade()` abaixo é REAL e
reversível. Não copie o padrão de `raise` das vizinhas para cá: aqui ele
seria mentira.

O índice de `sku` é ÚNICO PARCIAL (`WHERE sku <> ''`). Medido: o
`commerce_db` do usuário já tem seis produtos semeados
(`app/seeds/products.py::SEED_PRODUCTS`), e a coluna nasce com
`server_default=''` para o ALTER TABLE poder ser NOT NULL. Um índice único
TOTAL falharia no segundo produto existente. O idioma é o mesmo de
`ix_payment_methods_one_default_per_user` (`942f75a9a3f2`).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "b1a2c3d4e5f6"
down_revision: str | Sequence[str] | None = "c90210e9965c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Fornecedor vira parceiro: origem de expedição ────────────────────
    op.add_column(
        "fornecedores",
        sa.Column(
            "origem_rotulo", sa.String(length=120), nullable=False, server_default=sa.text("''")
        ),
    )
    op.add_column("fornecedores", sa.Column("origem_lat", sa.Numeric(9, 6), nullable=True))
    op.add_column("fornecedores", sa.Column("origem_lng", sa.Numeric(9, 6), nullable=True))

    # ── Produto ganha sku e active ───────────────────────────────────────
    op.add_column(
        "products",
        sa.Column("sku", sa.String(length=60), nullable=False, server_default=sa.text("''")),
    )
    op.add_column(
        "products",
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index(
        "uq_products_sku",
        "products",
        ["sku"],
        unique=True,
        postgresql_where=sa.text("sku <> ''"),
    )

    # ── Estoque ganha piso de reposição ──────────────────────────────────
    op.add_column(
        "estoque",
        sa.Column("estoque_minimo", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )

    # ── Trilha de auditoria de estoque ───────────────────────────────────
    op.create_table(
        "estoque_ajustes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("estoque_id", sa.Integer(), sa.ForeignKey("estoque.id"), nullable=False),
        sa.Column("quantidade_anterior", sa.Integer(), nullable=False),
        sa.Column("quantidade_nova", sa.Integer(), nullable=False),
        sa.Column("motivo", sa.String(length=300), nullable=False),
        sa.Column("autor_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_estoque_ajustes_estoque_id", "estoque_ajustes", ["estoque_id"])
    op.create_index("ix_estoque_ajustes_autor_id", "estoque_ajustes", ["autor_id"])

    # ── Transportadora ───────────────────────────────────────────────────
    op.create_table(
        "carriers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("location", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column(
            "average_delivery_days", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("rating", sa.Numeric(2, 1), nullable=False, server_default=sa.text("0")),
        sa.Column("sla_percentage", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default=sa.text("'ACTIVE'")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_carriers_name", "carriers", ["name"])
    op.create_index("ix_carriers_status", "carriers", ["status"])

    # ── Ocorrência ganha a dimensão de transportadora ────────────────────
    op.add_column("ocorrencias", sa.Column("transportadora_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_ocorrencias_transportadora_id",
        "ocorrencias",
        "carriers",
        ["transportadora_id"],
        ["id"],
    )
    op.create_index("ix_ocorrencias_transportadora_id", "ocorrencias", ["transportadora_id"])

    # ── Pedido carrega a origem congelada ────────────────────────────────
    op.add_column("orders", sa.Column("origem_rotulo", sa.String(length=120), nullable=True))
    op.add_column("orders", sa.Column("origem_lat", sa.Numeric(9, 6), nullable=True))
    op.add_column("orders", sa.Column("origem_lng", sa.Numeric(9, 6), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "origem_lng")
    op.drop_column("orders", "origem_lat")
    op.drop_column("orders", "origem_rotulo")

    op.drop_index("ix_ocorrencias_transportadora_id", table_name="ocorrencias")
    op.drop_constraint("fk_ocorrencias_transportadora_id", "ocorrencias", type_="foreignkey")
    op.drop_column("ocorrencias", "transportadora_id")

    op.drop_index("ix_carriers_status", table_name="carriers")
    op.drop_index("ix_carriers_name", table_name="carriers")
    op.drop_table("carriers")

    op.drop_index("ix_estoque_ajustes_autor_id", table_name="estoque_ajustes")
    op.drop_index("ix_estoque_ajustes_estoque_id", table_name="estoque_ajustes")
    op.drop_table("estoque_ajustes")

    op.drop_column("estoque", "estoque_minimo")

    op.drop_index("uq_products_sku", table_name="products")
    op.drop_column("products", "active")
    op.drop_column("products", "sku")

    op.drop_column("fornecedores", "origem_lng")
    op.drop_column("fornecedores", "origem_lat")
    op.drop_column("fornecedores", "origem_rotulo")
