"""pedido_status_historico order_id not null

Revision ID: c90210e9965c
Revises: 73f26f88d679
Create Date: 2026-08-10 00:05:00.000000

Dívida de schema #2 da task C10 (decisão do usuário, 2026-08-09):
`pedido_status_historico.order_id` vira `NOT NULL`. Era nullable, e foi
exatamente isso que deixou o bug de flush da task C6 gravar linha de
histórico com `order_id=NULL` em silêncio em vez de levantar.

`pedido_status_historico` tem 0 linhas no `commerce_db` real — medido neste
turno com o comando permitido:

    docker exec -i edu-postgres psql -U edu -d commerce_db -c \\
        "SELECT count(*) FROM pedido_status_historico;"
     count
    -------
         0

Zero, então `ALTER COLUMN ... SET NOT NULL` não precisa de backfill nem de
guard: não há linha NULL pré-existente para o `ALTER` rejeitar ou para um
`server_default` (que não protegeria `SET NOT NULL` de qualquer forma —
medido duas vezes no bloco B) teria que cobrir.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c90210e9965c"
down_revision: str | Sequence[str] | None = "73f26f88d679"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("pedido_status_historico", "order_id", existing_type=sa.UUID(), nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("pedido_status_historico", "order_id", existing_type=sa.UUID(), nullable=True)
