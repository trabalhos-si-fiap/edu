"""orders uuid pk

Revision ID: bd410bba0e85
Revises: 39d3b55161af
Create Date: 2026-08-08 22:33:02.418771

Reconstrução declarada, não sequência de ALTER com conversão de tipo. Mesmo
padrão da revision 1308bb221890 (`products`), com outras tabelas, outras
colunas e outros nomes de constraint.

A contagem de linhas nas quatro tabelas afetadas foi medida no `commerce_db`
real com

    docker exec -i edu-postgres psql -U edu -d commerce_db -c "
      SELECT 'pedidos' AS t, count(*) FROM pedidos
      UNION ALL SELECT 'pedido_itens', count(*) FROM pedido_itens
      UNION ALL SELECT 'pedido_status_historico', count(*) FROM pedido_status_historico
      UNION ALL SELECT 'ocorrencias', count(*) FROM ocorrencias;"

e deu zero nas quatro. Os nomes ali ainda são `pedidos`/`pedido_itens`
porque aquele banco está na revision de baseline `62926745dd94` (medido:
`SELECT version_num FROM alembic_version;` devolve `62926745dd94`), então
nem a 39d3b55161af (o rename para `orders`/`order_items`) nem nenhuma outra
do bloco B foi aplicada lá — são as mesmas linhas físicas, só com o nome
antigo. Isso não prova que o banco nunca teve dado — só que está vazio
agora. É essa condição, zero linhas no momento em que esta revision roda,
que o `upgrade` abaixo verifica antes de destruir qualquer coisa.

Se algum dia esta revision rodar contra um banco com dado, ela o apaga. Por
isso o `upgrade` começa checando, e falha alto em vez de destruir em
silêncio.

Nomes de constraint, nulidade de coluna e nomes de sequência foram medidos
num banco descartável (`syncchk_c3`, dropado ao final da task) construído
com `alembic upgrade head` na revision 39d3b55161af — o estado
imediatamente anterior a esta. Ver task-C3-report.md para a saída literal
de cada `\\d`. O achado que a task C2 deixou registrado se confirmou: o
`ALTER TABLE ... RENAME` do Postgres NÃO renomeia constraints, PK nem
sequências, então os nomes reais continuam em português sobre tabelas em
inglês, e NÃO seguem o nome atual da tabela nem o nome atual da coluna:

- `orders`: PK `pedidos_pkey`, sequência `pedidos_id_seq`
- `order_items`: PK `pedido_itens_pkey`, sequência `pedido_itens_id_seq`, e
  a FK para `orders` chama-se `pedido_itens_pedido_id_fkey` embora a coluna
  já se chame `order_id`
- `pedido_status_historico`: FK `pedido_status_historico_pedido_id_fkey`,
  idem — coluna já é `order_id`
- `ocorrencias`: FK `ocorrencias_pedido_id_fkey` (aqui coluna e constraint
  batem, porque `ocorrencias.pedido_id` não foi renomeada)

Uma diferença material em relação à 1308bb221890, onde as quatro colunas
referenciadoras eram todas nullable: `ocorrencias.pedido_id` é NOT NULL
(medido em `\\d ocorrencias`: `pedido_id | integer | | not null |`). O
`USING NULL` abaixo ainda é válido sobre ela porque a tabela está vazia — a
expressão do `USING` é avaliada por linha e o NOT NULL é checado por linha,
então com zero linhas nenhuma das duas coisas dispara. Medido num banco
descartável separado (`nulltest_c3`, também dropado):

    CREATE TABLE t (x integer NOT NULL);
    ALTER TABLE t ALTER COLUMN x TYPE uuid USING NULL;   -- ALTER TABLE

e o `\\d t` depois mostra `x | uuid | | not null |`: o NOT NULL sobrevive à
conversão. É mais uma razão para o guard de linhas rodar primeiro — com
dado, este mesmo ALTER falharia em vez de apagar em silêncio.

`gen_random_uuid()` é nativo do PostgreSQL 17.4, sem precisar da extensão
`pgcrypto` — medição da task B4, reaproveitada aqui porque é o mesmo
servidor.

Nada referencia `order_items.id`: `\\d order_items` não tem seção
"Referenced by". Por isso a troca de tipo da PK dele não pede nenhum
drop/create de FK, só a queda da sequência.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bd410bba0e85"
down_revision: str | Sequence[str] | None = "39d3b55161af"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABELAS_AFETADAS = ("orders", "order_items", "pedido_status_historico", "ocorrencias")

# (nome real da constraint, tabela, coluna) — os nomes NÃO são deriváveis do
# nome da tabela nem do nome da coluna; saíram do `\d` no banco descartável
# (ver docstring do módulo).
_FKS_PARA_ORDERS = (
    ("pedido_itens_pedido_id_fkey", "order_items", "order_id"),
    ("pedido_status_historico_pedido_id_fkey", "pedido_status_historico", "order_id"),
    ("ocorrencias_pedido_id_fkey", "ocorrencias", "pedido_id"),
)


def _falhar_se_houver_dado(conn) -> None:
    for tabela in _TABELAS_AFETADAS:
        total = conn.execute(sa.text(f"SELECT count(*) FROM {tabela}")).scalar_one()
        if total:
            raise RuntimeError(
                f"{tabela} tem {total} linhas. Esta revision é uma reconstrução "
                "declarada e as apagaria. Ver .superpowers/sdd/"
                "2026-08-05-phase-2c-order-and-tracking/task-C3-report.md."
            )


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    _falhar_se_houver_dado(conn)

    # Ordem: solta as FKs, troca o tipo do lado referenciado, troca o tipo do
    # lado referenciador, refaz as FKs.
    for constraint, tabela, _coluna in _FKS_PARA_ORDERS:
        op.drop_constraint(constraint, tabela, type_="foreignkey")

    op.execute("ALTER TABLE orders ALTER COLUMN id DROP DEFAULT")
    op.execute("ALTER TABLE orders ALTER COLUMN id TYPE uuid USING gen_random_uuid()")
    op.execute("ALTER TABLE orders ALTER COLUMN id SET DEFAULT gen_random_uuid()")
    op.execute("DROP SEQUENCE IF EXISTS pedidos_id_seq")

    op.execute("ALTER TABLE order_items ALTER COLUMN id DROP DEFAULT")
    op.execute("ALTER TABLE order_items ALTER COLUMN id TYPE uuid USING gen_random_uuid()")
    op.execute("ALTER TABLE order_items ALTER COLUMN id SET DEFAULT gen_random_uuid()")
    op.execute("DROP SEQUENCE IF EXISTS pedido_itens_id_seq")

    for _constraint, tabela, coluna in _FKS_PARA_ORDERS:
        # `USING NULL` é válido mesmo sobre `ocorrencias.pedido_id`, que é NOT
        # NULL, porque a tabela está vazia — ver docstring do módulo.
        op.execute(f"ALTER TABLE {tabela} ALTER COLUMN {coluna} TYPE uuid USING NULL")

    for constraint, tabela, coluna in _FKS_PARA_ORDERS:
        op.create_foreign_key(constraint, tabela, "orders", [coluna], ["id"])


def downgrade() -> None:
    """Downgrade schema."""
    raise RuntimeError(
        "Sem downgrade: a conversão int -> uuid descartou os ids originais. "
        "Restaure de backup ou refaça a baseline."
    )
