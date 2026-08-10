"""drop order_items product_id fk

Revision ID: 73f26f88d679
Revises: 099099b0c1a8
Create Date: 2026-08-10 00:00:00.000000

Dívida de schema #1 da task C10 (decisão do usuário, 2026-08-09): derruba a
FK `order_items.product_id -> products.id`. `order_items` é o registro
histórico do que foi comprado — o catálogo (`products`) tem que poder mudar
por baixo, inclusive perder uma linha, sem quebrar o histórico. Com a FK
presente, apagar um produto referenciado por qualquer pedido levanta
`IntegrityError`/`ForeignKeyViolationError` (`update or delete on table
"products" violates foreign key constraint`), e o caminho "produto saiu do
catálogo é pulado" da recompra (task C7) fica inalcançável em produção. O
legacy nunca teve essa FK, de propósito, pelo mesmo motivo — medido em
`back-end/legacy/app/modules/orders/models.py:84`.

`product_id` continua `NOT NULL` e continua sendo snapshot — só o
`ForeignKey` sai. Nada além disso muda: sem coluna nova, sem guard de
reconstrução (dropar uma constraint não apaga linha nenhuma).

Nome da constraint medido num banco descartável construído pela cadeia real
(`syncchk_c10_commerce`, `alembic upgrade head` até `099099b0c1a8`, dropado
ao final da medição — ver task-C10-report.md):

    docker exec -i edu-postgres psql -U edu -d syncchk_c10_commerce -c \\
        "\\d order_items"
    ...
    Foreign-key constraints:
        "order_items_order_id_fkey" FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
        "pedido_itens_fornecedor_id_fkey" FOREIGN KEY (supplier_id) REFERENCES fornecedores(id)
        "pedido_itens_produto_id_fkey" FOREIGN KEY (product_id) REFERENCES products(id)

A FK de `product_id` ainda carrega o nome ANTIGO, `pedido_itens_produto_id_fkey`
— `ALTER TABLE ... RENAME` não renomeia constraint (mesma observação já
registrada em `39d3b55161af`/`099099b0c1a8`); ela nunca foi recriada desde a
rename `pedido_itens` -> `order_items`. É esse o nome que este `upgrade()`
dropa. Um banco construído por `Base.metadata.create_all()` (como
`tests/conftest.py` faz) nomearia a constraint `order_items_product_id_fkey`
em vez disso — por isso este nome só pôde ser medido contra a cadeia real de
migrations, não contra a suíte.

`downgrade()` — achado da revisão (fix round 1, Minor promovido #5): a
primeira versão só recriava a FK, sem guard. Isso é seguro SE nenhum
`order_items.product_id` órfão existir, mas essa é exatamente a situação
que esta migration existe para permitir — um `order_items` cujo produto foi
apagado do catálogo. Sobre um banco assim, `op.create_foreign_key`
estouraria `ForeignKeyViolationError` cru do Postgres, sem explicação
nenhuma. Diferente de `bd410bba0e85`/`099099b0c1a8` (conversões
irreversíveis por construção, `raise RuntimeError` incondicional), aqui o
downgrade É possível quando não há linha órfã — por isso o guard checa dado
de verdade, no mesmo espírito de `_falhar_se_houver_dado` daquelas
revisions, só que do lado do `downgrade()`.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "73f26f88d679"
down_revision: str | Sequence[str] | None = "099099b0c1a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FK_ORDER_ITEMS_PRODUCT_ID = "pedido_itens_produto_id_fkey"


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(_FK_ORDER_ITEMS_PRODUCT_ID, "order_items", type_="foreignkey")


def _falhar_se_downgrade_quebrar_referencia(conn) -> None:
    total = conn.execute(
        sa.text(
            "SELECT count(*) FROM order_items oi "
            "WHERE NOT EXISTS (SELECT 1 FROM products p WHERE p.id = oi.product_id)"
        )
    ).scalar_one()
    if total:
        raise RuntimeError(
            f"{total} linha(s) de order_items apontam para um product_id que não "
            "existe mais em products — exatamente o estado que esta migration existe "
            "para permitir. Recriar a FK order_items.product_id -> products.id "
            "estouraria ForeignKeyViolationError nessas linhas. Não há downgrade "
            "seguro sem antes resolver (ou apagar) essas linhas órfãs à mão."
        )


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    _falhar_se_downgrade_quebrar_referencia(conn)
    op.create_foreign_key(
        _FK_ORDER_ITEMS_PRODUCT_ID, "order_items", "products", ["product_id"], ["id"]
    )
