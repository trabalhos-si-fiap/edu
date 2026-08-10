"""notificacao pedido_id uuid

Revision ID: 886205d547cc
Revises: 7b44c873024d
Create Date: 2026-08-10 01:00:00.000000

Task C10: fecha um item do backlog da fase 4 — `data.order_id` chegava como
UUID string vindo do legacy e como inteiro vindo do notification-service,
mesma chave (`pedido_id`), tipo diferente. O commerce-service já publica os
cinco eventos de pedido com `pedido_id` string de UUID desde a task C3
(`orders.id` é UUID); esta migration faz o consumidor concordar.

`notificacoes` tem 0 linhas no `notification_db` real — medido neste turno
com o comando permitido:

    docker exec -i edu-postgres psql -U edu -d notification_db -c \\
        "SELECT count(*) AS total, count(pedido_id) AS com_pedido FROM notificacoes;"
     total | com_pedido
    -------+------------
         0 |          0

Zero HOJE — e "vazio hoje" não é "vazio no corte": o notification-service
está no ar consumindo `order.status_changed`, e cada notificação gravada
entre esta medição e o `upgrade head` do corte é uma linha a mais. Por isso
`upgrade()` NÃO confia na contagem congelada aqui: ele reconta em runtime e
recusa. `USING NULL` é conversão incondicional nas duas direções e não
existe conversão possível em nenhuma delas — um inteiro não vira UUID nem um
UUID vira inteiro —, então o guard é a única coisa entre a migration e a
perda silenciosa. `index=True` acompanha o model (`app/models/notificacao.py`)
— medido que nenhuma query filtra por `Notificacao.pedido_id` hoje
(`grep -rn "Notificacao.pedido_id\\|pedido_id ==" app/` vazio), então o
índice não tem leitor ainda; mantido por seguir o desenho do model, não por
necessidade medida.

`downgrade()` — achado da revisão (fix round 1, Minor promovido #5): a
primeira versão fazia `ALTER ... TYPE integer USING NULL` incondicional. Um
UUID não tem correspondência com nenhum inteiro válido — não é como a FK da
dívida #1 do commerce (onde o downgrade É seguro se não houver linha
órfã); aqui QUALQUER `pedido_id` preenchido é descartado, sempre, porque não
existe conversão de volta. O guard verifica se a coluna já tem dado de
verdade e recusa o downgrade nesse caso, em vez de perder o valor em
silêncio.

`upgrade()` — achado da revisão final da branch: o guard estava só no lado
que nunca roda. A cadeia do commerce protege o lado certo
(`bd410bba0e85_orders_uuid_pk.py` chama `_falhar_se_houver_dado` dentro do
`upgrade()`), e esta revision fazia o contrário. Agora as duas direções
recontam antes de qualquer `ALTER`, e o `RuntimeError` aborta a transação da
migration — o banco fica na revision anterior, com a linha intacta.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "886205d547cc"
down_revision: str | Sequence[str] | None = "7b44c873024d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _contar_pedido_id_preenchido(conn) -> int:
    return conn.execute(
        sa.text("SELECT count(*) FROM notificacoes WHERE pedido_id IS NOT NULL")
    ).scalar_one()


def _falhar_se_pedido_id_tiver_dado_no_upgrade(conn) -> None:
    total = _contar_pedido_id_preenchido(conn)
    if total:
        raise RuntimeError(
            f"{total} notificacoes têm pedido_id preenchido. Não há upgrade seguro: "
            "um inteiro não corresponde a nenhum UUID válido — "
            "'ALTER ... TYPE uuid USING NULL' descartaria esses valores em "
            "silêncio. Restaure de backup ou aceite a perda explicitamente."
        )


def _falhar_se_pedido_id_tiver_dado_no_downgrade(conn) -> None:
    total = _contar_pedido_id_preenchido(conn)
    if total:
        raise RuntimeError(
            f"{total} notificacoes têm pedido_id preenchido. Não há downgrade seguro: "
            "um UUID não corresponde a nenhum valor inteiro válido — "
            "'ALTER ... TYPE integer USING NULL' descartaria esses valores em "
            "silêncio. Restaure de backup ou aceite a perda explicitamente."
        )


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    _falhar_se_pedido_id_tiver_dado_no_upgrade(conn)
    op.alter_column(
        "notificacoes",
        "pedido_id",
        existing_type=sa.Integer(),
        type_=sa.UUID(),
        postgresql_using="NULL",
        existing_nullable=True,
    )
    op.create_index(op.f("ix_notificacoes_pedido_id"), "notificacoes", ["pedido_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    _falhar_se_pedido_id_tiver_dado_no_downgrade(conn)
    op.drop_index(op.f("ix_notificacoes_pedido_id"), table_name="notificacoes")
    op.alter_column(
        "notificacoes",
        "pedido_id",
        existing_type=sa.UUID(),
        type_=sa.Integer(),
        postgresql_using="NULL",
        existing_nullable=True,
    )
