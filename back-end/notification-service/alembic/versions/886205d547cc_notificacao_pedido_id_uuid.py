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

Zero, então `ALTER ... TYPE uuid USING NULL` basta: não há valor inteiro
antigo para preservar ou zerar explicitamente — `USING NULL` é uma
conversão incondicional, mas com a tabela vazia ela não descarta nenhuma
referência real. `index=True` acompanha o model (`app/models/notificacao.py`)
— medido que nenhuma query filtra por `Notificacao.pedido_id` hoje
(`grep -rn "Notificacao.pedido_id\\|pedido_id ==" app/` vazio), então o
índice não tem leitor ainda; mantido por seguir o desenho do model, não por
necessidade medida.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "886205d547cc"
down_revision: str | Sequence[str] | None = "7b44c873024d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
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
    op.drop_index(op.f("ix_notificacoes_pedido_id"), table_name="notificacoes")
    op.alter_column(
        "notificacoes",
        "pedido_id",
        existing_type=sa.UUID(),
        type_=sa.Integer(),
        postgresql_using="NULL",
        existing_nullable=True,
    )
