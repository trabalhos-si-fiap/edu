"""products uuid pk

Revision ID: 1308bb221890
Revises: 77290516f1b1
Create Date: 2026-08-07 10:23:51.471483

Reconstrução declarada, não sequência de ALTER com conversão de tipo.

A contagem de linhas nas quatro tabelas afetadas foi medida no `commerce_db`
real (task B4/Step 1) e deu zero em `produtos` (nome real da tabela lá — a
revision 77290516f1b1 nunca foi aplicada a esse banco), `estoque`,
`pedido_itens` e `ocorrencias`. `commerce-service` não tem script de seed
(nenhum arquivo de seed no diretório do serviço) e
`postgres/initdb.d/10-create-service-databases.sh` só executa `CREATE
DATABASE`, sem `INSERT`. Isso não prova que o banco nunca teve dado — só
que está vazio agora. É essa condição, zero linhas no momento em que esta
revision roda, que o `upgrade` abaixo verifica antes de destruir qualquer
coisa.

Se algum dia esta revision rodar contra um banco com dado, ela o apaga. Por
isso o `upgrade` começa checando, e falha alto em vez de destruir em
silêncio.

Nomes de constraint, nulidade de coluna, nome de sequência e disponibilidade
de `gen_random_uuid()` foram medidos num banco descartável
(`syncchk_commerce_b4`, dropado ao final da task) na revisão 77290516f1b1
(o estado imediatamente anterior a esta) — ver task-B4-report.md para a
saída literal de cada `\\d`. As quatro constraints batem exatamente com os
nomes-padrão do Postgres (`estoque_produto_id_fkey`,
`pedido_itens_produto_id_fkey`, `ocorrencias_produto_id_fkey`,
`ocorrencias_produto_escolhido_id_fkey`); as quatro colunas referenciadoras
são nullable; `gen_random_uuid()` existe nativamente (PostgreSQL 17.4, sem
precisar da extensão `pgcrypto`); e a sequência de `products.id` chama-se
`produtos_id_seq` — o rename de tabela da revision anterior não a renomeou.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1308bb221890"
down_revision: str | Sequence[str] | None = "77290516f1b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABELAS_AFETADAS = ("products", "estoque", "pedido_itens", "ocorrencias")


def _falhar_se_houver_dado(conn) -> None:
    for tabela in _TABELAS_AFETADAS:
        total = conn.execute(sa.text(f"SELECT count(*) FROM {tabela}")).scalar_one()
        if total:
            raise RuntimeError(
                f"{tabela} tem {total} linhas. Esta revision é uma reconstrução "
                "declarada e as apagaria. Ver .superpowers/sdd/"
                "2026-08-05-phase-2b-catalog-and-cart/task-B4-report.md."
            )


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    _falhar_se_houver_dado(conn)

    # Ordem: solta as FKs, troca o tipo do lado referenciado, troca o tipo do
    # lado referenciador, refaz as FKs. Nomes de constraint confirmados no
    # banco descartável (ver docstring do módulo).
    op.drop_constraint("estoque_produto_id_fkey", "estoque", type_="foreignkey")
    op.drop_constraint("pedido_itens_produto_id_fkey", "pedido_itens", type_="foreignkey")
    op.drop_constraint("ocorrencias_produto_id_fkey", "ocorrencias", type_="foreignkey")
    op.drop_constraint("ocorrencias_produto_escolhido_id_fkey", "ocorrencias", type_="foreignkey")

    op.execute("ALTER TABLE products ALTER COLUMN id DROP DEFAULT")
    op.execute("ALTER TABLE products ALTER COLUMN id TYPE uuid USING gen_random_uuid()")
    op.execute("ALTER TABLE products ALTER COLUMN id SET DEFAULT gen_random_uuid()")
    # Nome real confirmado no banco descartável: o rename produtos->products
    # (revision anterior) não renomeou a sequência.
    op.execute("DROP SEQUENCE IF EXISTS produtos_id_seq")

    for tabela, coluna in (
        ("estoque", "produto_id"),
        ("pedido_itens", "produto_id"),
        ("ocorrencias", "produto_id"),
        ("ocorrencias", "produto_escolhido_id"),
    ):
        # `USING NULL` só é válido porque as quatro colunas são nullable —
        # confirmado no banco descartável (ver docstring do módulo).
        op.execute(f"ALTER TABLE {tabela} ALTER COLUMN {coluna} TYPE uuid USING NULL")

    op.create_foreign_key("estoque_produto_id_fkey", "estoque", "products", ["produto_id"], ["id"])
    op.create_foreign_key(
        "pedido_itens_produto_id_fkey", "pedido_itens", "products", ["produto_id"], ["id"]
    )
    op.create_foreign_key(
        "ocorrencias_produto_id_fkey", "ocorrencias", "products", ["produto_id"], ["id"]
    )
    op.create_foreign_key(
        "ocorrencias_produto_escolhido_id_fkey",
        "ocorrencias",
        "products",
        ["produto_escolhido_id"],
        ["id"],
    )

    # `produtos_sugeridos` é JSONB com lista de ids. Sem dado (confirmado
    # acima), basta zerar.
    op.execute("UPDATE ocorrencias SET produtos_sugeridos = NULL")


def downgrade() -> None:
    """Downgrade schema."""
    raise RuntimeError(
        "Sem downgrade: a conversão int -> uuid descartou os ids originais. "
        "Restaure de backup ou refaça a baseline."
    )
