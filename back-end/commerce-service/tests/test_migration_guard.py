"""Trava do guard de linhas da revision `bd410bba0e85_orders_uuid_pk`.

ESCOPO DESTE ARQUIVO — leia antes de confiar nele: ele exercita **só a
lógica do `_falhar_se_houver_dado`**, com uma conexão de mentira. Ele NÃO
roda a migration, NÃO toca em banco nenhum e NÃO prova que o `upgrade()`
funciona.

Cobertura fim-a-fim da migration continua AUSENTE, de propósito e por
enquanto: `tests/conftest.py` monta o schema com
`Base.metadata.create_all` e nunca invoca o alembic, então nenhuma revision
deste serviço é executada pela suíte. A aplicação da `bd410bba0e85` foi
verificada à mão, contra um banco descartável (`syncchk_c3`), e está
registrada em task-C3-report.md — não aqui.

O que este arquivo trava é o que mais importa e o que mais barato quebra em
silêncio: que o guard REALMENTE levanta quando encontra linha, e REALMENTE
deixa passar quando não encontra. A revision é uma reconstrução declarada —
ela apaga dado por construção — e o guard é a única coisa entre ela e uma
perda irreversível. Medido no fix round 1 da task C3: com dado presente, as
colunas nullable (`order_items.order_id`,
`pedido_status_historico.order_id`) NÃO fazem o `ALTER ... USING NULL`
falhar; ele passa e apaga o vínculo em silêncio. Em dois dos três casos o
Postgres não protege nada — só este guard protege.
"""

import importlib.util
from pathlib import Path

import pytest

_REVISION = (
    Path(__file__).resolve().parents[1] / "alembic" / "versions" / "bd410bba0e85_orders_uuid_pk.py"
)


def _carregar_revision():
    """Carrega o módulo da revision pelo caminho.

    `alembic/versions/` não é um pacote importável (sem `__init__.py`, e
    fora do `sys.path`), então `import` normal não alcança. Carregar pelo
    arquivo mantém o teste amarrado à revision REAL — se alguém apagar ou
    renomear o arquivo, isto falha alto em vez de testar uma cópia.
    """
    spec = importlib.util.spec_from_file_location("revision_orders_uuid_pk", _REVISION)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class _FakeResult:
    def __init__(self, total: int) -> None:
        self._total = total

    def scalar_one(self) -> int:
        return self._total


class _FakeConn:
    """Conexão de mentira: devolve uma contagem pré-programada por consulta.

    Só precisa do que o guard usa — `execute(...).scalar_one()`. Guarda o
    SQL recebido para que o teste possa provar QUAIS tabelas foram
    consultadas, não só quantas.
    """

    def __init__(self, totais: list[int]) -> None:
        self._totais = list(totais)
        self.consultas: list[str] = []

    def execute(self, clause):
        self.consultas.append(str(clause))
        return _FakeResult(self._totais.pop(0))


def test_the_guard_allows_the_migration_through_when_every_table_is_empty():
    revision = _carregar_revision()
    conn = _FakeConn([0, 0, 0, 0])

    revision._falhar_se_houver_dado(conn)  # não deve levantar

    # As QUATRO tabelas afetadas têm que ser consultadas — um guard que
    # checasse três passaria a deixar a quarta ser apagada em silêncio.
    assert len(conn.consultas) == 4
    for tabela in ("orders", "order_items", "pedido_status_historico", "ocorrencias"):
        assert any(tabela in sql for sql in conn.consultas), tabela


def test_the_guard_raises_before_destroying_anything_when_a_table_has_rows():
    revision = _carregar_revision()
    # `orders` vazia, `order_items` com 3 linhas — o guard tem que parar na
    # segunda e nunca chegar às duas últimas.
    conn = _FakeConn([0, 3, 0, 0])

    with pytest.raises(RuntimeError) as erro:
        revision._falhar_se_houver_dado(conn)

    mensagem = str(erro.value)
    assert "order_items" in mensagem
    assert "3" in mensagem
    # Parou na tabela que tinha dado, sem consultar o resto.
    assert len(conn.consultas) == 2


def test_the_guard_covers_exactly_the_four_tables_the_migration_rewrites():
    """`_TABELAS_AFETADAS` e as tabelas que o `upgrade()` de fato reescreve
    têm que ser o mesmo conjunto. Se alguém acrescentar uma tabela à
    migration e esquecer do guard, ela passa a ser apagada sem checagem."""
    revision = _carregar_revision()

    assert set(revision._TABELAS_AFETADAS) == {
        "orders",
        "order_items",
        "pedido_status_historico",
        "ocorrencias",
    }
