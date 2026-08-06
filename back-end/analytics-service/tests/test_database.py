"""Testa a fábrica de sessão de `app/database.py` sem depender do banco.

Task 20 troca `sessionmaker(engine, class_=AsyncSession, ...)` (forma 1.4) por
`async_sessionmaker(engine, ...)` (forma 2.x). As duas produzem `AsyncSession`
em runtime com o mesmo `async with async_session() as s`, e nenhum teste
existente cobria a diferença: `app/events/consumer.py` sempre troca
`async_session` por `test_session_factory` via `monkeypatch` (ver
`tests/test_consumer.py`), e `get_db` é sempre sobrescrito por
`_override_get_db` na fixture `client` — o objeto real exportado por
`app/database.py` nunca era exercitado sem substituição.

`isinstance` é o único jeito de observar a troca em runtime: os dois tipos
aceitam a mesma chamada, então só a identidade da classe distingue um do
outro. Este teste substitui o Step 4 do brief (que confirmaria o mesmo ponto
subindo containers via `docker compose`) — não roda neste worktree porque
`back-end/.env` não existe aqui (ver task-20-report.md).
"""

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database import async_session


def test_async_session_is_the_typed_2x_factory():
    assert isinstance(async_session, async_sessionmaker)
