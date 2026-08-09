"""orders shipping and item snapshot

Revision ID: 099099b0c1a8
Revises: bd410bba0e85
Create Date: 2026-08-09 14:10:44.558987

`orders.endereco_entrega` (texto livre) vira os oito `ship_*` nullable do
legacy, mais `payment_method` e `status_updated_at`. `order_items` ganha o
snapshot do produto (`product_name`, `image_url`, `rating_avg`,
`rating_count`), e `order_id`/`product_id` passam a `NOT NULL` com índice e
`ondelete="CASCADE"` na FK de `order_id` — ver app/models/pedido.py (task
C4) para o porquê de cada campo.

QUARTA parede da cadeia de reconstruções declaradas (B4, C3, e a rename da
C2 antes dela) — `drop_column("orders", "endereco_entrega")` apaga dado por
construção se houver linha. Mesmo padrão da `bd410bba0e85_orders_uuid_pk.py`
(C3): `_TABELAS_AFETADAS`, `_falhar_se_houver_dado(conn)` levantando
`RuntimeError` antes de qualquer DDL, e downgrade que recusa.

Contagem medida no `commerce_db` real, ANTES de qualquer migration do bloco
B ou C (banco na revision de baseline `62926745dd94`, nomes ainda em
português):

    docker exec -i edu-postgres psql -U edu -d commerce_db -c \
        "SELECT version_num FROM alembic_version;"
    -- 62926745dd94
    docker exec -i edu-postgres psql -U edu -d commerce_db -c \
        "SELECT count(*) FROM pedidos;"
    -- 0
    docker exec -i edu-postgres psql -U edu -d commerce_db -c \
        "SELECT count(*) FROM pedido_itens;"
    -- 0

zero nas duas — mesma medição que C0 e C3 já registraram. Isso não prova que
o banco nunca teve dado, só que está vazio agora; é essa condição, checada
de novo em runtime por `_falhar_se_houver_dado`, que o `upgrade()` exige
antes de destruir qualquer coisa.

`_TABELAS_AFETADAS` cobre `orders` E `order_items`, embora só `orders` perca
dado em SILÊNCIO: o `drop_column` de `endereco_entrega` apaga a string sem
erro nenhum. Em `order_items`, `product_name NOT NULL` sem default e
`order_id`/`product_id ALTER ... SET NOT NULL` sobre uma tabela com linha
NULL nessas colunas FALHAM alto (Postgres verifica NOT NULL por linha no
próprio ALTER) — não é o mesmo risco de `bd410bba0e85`, onde duas das três
colunas convertidas (nullable) engoliam o vínculo em silêncio via
`USING NULL`; aqui não há `USING`, é `SET NOT NULL` direto, que sempre
verifica. Incluído mesmo assim por padrão de defesa em profundidade
(mesma decisão que C3 tomou para `ocorrencias.pedido_id`, também NOT NULL
e também protegida pelo próprio Postgres) e porque `order_items` está na
mesma medição de contagem zero acima.

`server_default` em toda coluna nova `NOT NULL`, seguindo
`app/models/pedido.py`: `payment_method`, `status_updated_at`, `image_url`,
`rating_avg`, `rating_count`. EXCEÇÃO deliberada: `product_name` fica
`NOT NULL` SEM `server_default`. A tabela está vazia (medido acima), então
não há linha para preencher, e o legacy declara o mesmo campo assim —
`back-end/legacy/app/modules/orders/models.py:86`:
`product_name: Mapped[str] = mapped_column(String(160), nullable=False)`,
sem default nenhum. Um snapshot que aceitasse nome vazio por padrão não
seria snapshot.

Nomes de constraint medidos num banco descartável (`calib_c4`, construído
com `alembic upgrade head` na revision `bd410bba0e85` — o estado
imediatamente anterior a esta — e dropado ao final da calibração; ver
task-C4-report.md): a FK de `order_items.order_id` para `orders` ainda se
chama `pedido_itens_pedido_id_fkey` (achado da C2/C3 confirmado de novo:
`ALTER TABLE ... RENAME` não renomeia constraint). Este arquivo a substitui
por `order_items_order_id_fkey` (nome que o Postgres teria escolhido
sozinho para uma FK nova sobre uma coluna já chamada `order_id`), agora com
`ondelete="CASCADE"` — a FK atual não tem.

Um autogenerate calibrado contra esse mesmo banco descartável (antes deste
arquivo existir) confirmou que o instrumento ENXERGA a mudança inteira:
14 colunas novas (10 em `orders`, 4 em `order_items`), não 11 como o plano
desta task previa sem medir — 10 (`payment_method`, `status_updated_at`,
os 8 `ship_*`) + 4 (`product_name`, `image_url`, `rating_avg`,
`rating_count`) = 14. A previsão de "onze" caiu por medição, igual outras
do controlador; corrigida aqui e no relatório da task, não silenciada.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "099099b0c1a8"
down_revision: str | Sequence[str] | None = "bd410bba0e85"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABELAS_AFETADAS = ("orders", "order_items")

_FK_ORDER_ITEMS_ORDER_ID_ANTIGA = "pedido_itens_pedido_id_fkey"
_FK_ORDER_ITEMS_ORDER_ID_NOVA = "order_items_order_id_fkey"


def _falhar_se_houver_dado(conn) -> None:
    for tabela in _TABELAS_AFETADAS:
        total = conn.execute(sa.text(f"SELECT count(*) FROM {tabela}")).scalar_one()
        if total:
            raise RuntimeError(
                f"{tabela} tem {total} linhas. Esta revision é uma reconstrução "
                "declarada e as apagaria (drop_column de endereco_entrega e/ou "
                "ALTER ... SET NOT NULL sobre order_id/product_id). Ver "
                ".superpowers/sdd/2026-08-05-phase-2c-order-and-tracking/"
                "task-C4-report.md."
            )


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    _falhar_se_houver_dado(conn)

    # ── order_items: snapshot do produto ────────────────────────────────
    op.add_column("order_items", sa.Column("product_name", sa.String(length=160), nullable=False))
    op.add_column(
        "order_items",
        sa.Column(
            "image_url",
            sa.String(length=512),
            server_default=sa.text("''"),
            nullable=False,
        ),
    )
    op.add_column(
        "order_items",
        sa.Column(
            "rating_avg",
            sa.Numeric(precision=3, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "order_items",
        sa.Column("rating_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )

    # order_id/product_id passam a NOT NULL + índice em order_id + FK com
    # ondelete=CASCADE (ver docstring do módulo para os nomes medidos).
    op.alter_column("order_items", "order_id", existing_type=sa.UUID(), nullable=False)
    op.alter_column("order_items", "product_id", existing_type=sa.UUID(), nullable=False)
    op.create_index(op.f("ix_order_items_order_id"), "order_items", ["order_id"], unique=False)
    op.drop_constraint(_FK_ORDER_ITEMS_ORDER_ID_ANTIGA, "order_items", type_="foreignkey")
    op.create_foreign_key(
        _FK_ORDER_ITEMS_ORDER_ID_NOVA,
        "order_items",
        "orders",
        ["order_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # ── orders: payment_method, status_updated_at, ship_* ───────────────
    op.add_column(
        "orders",
        sa.Column(
            "payment_method",
            sa.String(length=120),
            server_default=sa.text("''"),
            nullable=False,
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "status_updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column("orders", sa.Column("ship_label", sa.String(length=60), nullable=True))
    op.add_column("orders", sa.Column("ship_zip_code", sa.String(length=9), nullable=True))
    op.add_column("orders", sa.Column("ship_street", sa.String(length=160), nullable=True))
    op.add_column("orders", sa.Column("ship_number", sa.String(length=20), nullable=True))
    op.add_column("orders", sa.Column("ship_complement", sa.String(length=120), nullable=True))
    op.add_column("orders", sa.Column("ship_neighborhood", sa.String(length=120), nullable=True))
    op.add_column("orders", sa.Column("ship_city", sa.String(length=120), nullable=True))
    op.add_column("orders", sa.Column("ship_state", sa.String(length=2), nullable=True))

    # A destrutiva de verdade, por último: já passamos pelo guard acima.
    op.drop_column("orders", "endereco_entrega")


def downgrade() -> None:
    """Downgrade schema."""
    raise RuntimeError(
        "Sem downgrade: endereco_entrega foi descartada por construção "
        "(reconstrução declarada, mesma família de bd410bba0e85/C3). Restaurar "
        "a coluna sem o texto original seria pior que não restaurar — "
        "recriaria um contrato que parece íntegro mas está vazio. Refaça a "
        "baseline ou restaure de backup."
    )
