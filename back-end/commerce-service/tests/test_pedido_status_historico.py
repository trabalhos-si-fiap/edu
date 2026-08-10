"""Dívida de schema #2 do commerce, decisão do usuário (2026-08-09, task
C10): `PedidoStatusHistorico.order_id` tem que ser `NOT NULL`. Nullable foi
o que deixou o bug de flush da C6 gravar linha de histórico com
`order_id=NULL` em silêncio em vez de levantar.

Migration própria:
`alembic/versions/c90210e9965c_pedido_status_historico_order_id_not_null.py`,
encadeada depois de `73f26f88d679` (a da dívida #1).
"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.pedido import PedidoStatusHistorico


async def test_order_history_without_order_id_is_rejected(db_session):
    """`order_id` nullable foi o que deixou o bug de flush da C6 gravar
    histórico com `order_id=NULL` em silêncio. Depois da migration, inserir
    sem `order_id` tem que levantar `IntegrityError`. Hoje (nullable) não
    levanta: este teste prova o RED antes da migration."""
    with pytest.raises(IntegrityError):
        db_session.add(
            PedidoStatusHistorico(
                order_id=None,
                status="CRIADO",
                user_id=str(uuid.uuid4()),
            )
        )
        await db_session.commit()
