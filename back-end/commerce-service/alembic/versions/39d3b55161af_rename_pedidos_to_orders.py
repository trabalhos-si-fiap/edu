"""rename pedidos to orders

Revision ID: 39d3b55161af
Revises: 942f75a9a3f2
Create Date: 2026-08-08 12:18:17.942339

Rename mecânico, sem mudança de tipo e sem coluna nova. `pedido_status_historico`
NÃO muda de nome (agregado sem cliente) — só o FK `pedido_id` -> `order_id`.
`ocorrencias.pedido_id` também mantém o nome; só o alvo do FK acompanha, e isso
o Postgres faz sozinho no `RENAME TO` (o catálogo guarda o OID da tabela, não o
nome), então não há DDL para ele aqui.

`fornecedor_id` -> `supplier_id` é SÓ rename: a coluna já era nullable. Medido na
cadeia aplicada a um banco descartável, não no banco de dev (que está sete
migrations atrás, na baseline `62926745dd94`):

    docker exec -i edu-postgres psql -U edu -d syncchk_c2 -c "\\d pedido_itens"
     fornecedor_id  | integer       |           |          |

— coluna sem `not null`. Por isso NÃO há `alter_column(..., nullable=...)` aqui
nem no `downgrade`.

Os quatro `ALTER INDEX` existem porque `ALTER TABLE ... RENAME` do Postgres
renomeia a tabela e as colunas mas NÃO renomeia os índices. Sem eles o banco
ficaria com `ix_pedidos_aluno_id` enquanto o model declara `index=True` em
`Order.user_id` (que o SQLAlchemy nomeia `ix_orders_user_id`), e o
`alembic revision --autogenerate` de sincronia sairia com um par
drop_index/create_index em vez de vazio. Nomes reais lidos com
`docker exec -i edu-postgres psql -U edu -d syncchk_c2 -c "\\d pedidos"`.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "39d3b55161af"
down_revision: str | Sequence[str] | None = "942f75a9a3f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table("pedidos", "orders")
    op.alter_column("orders", "aluno_id", new_column_name="user_id")
    op.alter_column("orders", "valor_total", new_column_name="total")
    op.alter_column("orders", "separador_id", new_column_name="picker_id")
    op.alter_column("orders", "entregador_id", new_column_name="deliverer_id")
    op.alter_column("orders", "transportadora_nome", new_column_name="carrier_name")
    op.alter_column("orders", "data_prevista_entrega", new_column_name="estimated_delivery_at")
    op.alter_column("orders", "criado_em", new_column_name="created_at")
    op.alter_column("orders", "atualizado_em", new_column_name="updated_at")

    op.execute("ALTER INDEX ix_pedidos_aluno_id RENAME TO ix_orders_user_id")
    op.execute("ALTER INDEX ix_pedidos_separador_id RENAME TO ix_orders_picker_id")
    op.execute("ALTER INDEX ix_pedidos_entregador_id RENAME TO ix_orders_deliverer_id")
    op.execute("ALTER INDEX ix_pedidos_status RENAME TO ix_orders_status")

    op.rename_table("pedido_itens", "order_items")
    op.alter_column("order_items", "pedido_id", new_column_name="order_id")
    op.alter_column("order_items", "produto_id", new_column_name="product_id")
    op.alter_column("order_items", "fornecedor_id", new_column_name="supplier_id")
    op.alter_column("order_items", "quantidade", new_column_name="quantity")
    op.alter_column("order_items", "preco_unitario", new_column_name="unit_price")

    op.alter_column("pedido_status_historico", "pedido_id", new_column_name="order_id")


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("pedido_status_historico", "order_id", new_column_name="pedido_id")

    op.alter_column("order_items", "unit_price", new_column_name="preco_unitario")
    op.alter_column("order_items", "quantity", new_column_name="quantidade")
    op.alter_column("order_items", "supplier_id", new_column_name="fornecedor_id")
    op.alter_column("order_items", "product_id", new_column_name="produto_id")
    op.alter_column("order_items", "order_id", new_column_name="pedido_id")
    op.rename_table("order_items", "pedido_itens")

    op.execute("ALTER INDEX ix_orders_status RENAME TO ix_pedidos_status")
    op.execute("ALTER INDEX ix_orders_deliverer_id RENAME TO ix_pedidos_entregador_id")
    op.execute("ALTER INDEX ix_orders_picker_id RENAME TO ix_pedidos_separador_id")
    op.execute("ALTER INDEX ix_orders_user_id RENAME TO ix_pedidos_aluno_id")

    op.alter_column("orders", "updated_at", new_column_name="atualizado_em")
    op.alter_column("orders", "created_at", new_column_name="criado_em")
    op.alter_column("orders", "estimated_delivery_at", new_column_name="data_prevista_entrega")
    op.alter_column("orders", "carrier_name", new_column_name="transportadora_nome")
    op.alter_column("orders", "deliverer_id", new_column_name="entregador_id")
    op.alter_column("orders", "picker_id", new_column_name="separador_id")
    op.alter_column("orders", "total", new_column_name="valor_total")
    op.alter_column("orders", "user_id", new_column_name="aluno_id")
    op.rename_table("orders", "pedidos")
