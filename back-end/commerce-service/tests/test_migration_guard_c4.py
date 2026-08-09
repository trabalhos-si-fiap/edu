"""Trava do guard de linhas da revision
`099099b0c1a8_orders_shipping_and_item_snapshot` (task C4).

ESCOPO DESTE ARQUIVO — leia antes de confiar nele: ele exercita só a lógica
de `_falhar_se_houver_dado`, com uma conexão de mentira. Ele NÃO roda a
migration, NÃO toca em banco nenhum e NÃO prova que o `upgrade()` funciona.
Mesmo escopo declarado que `tests/test_migration_guard.py` (C3) já assume
para a revision anterior — ver o docstring de lá para o porquê de
`tests/conftest.py` não cobrir isso (monta o schema com
`Base.metadata.create_all`, nunca invoca o alembic).

A aplicação de `099099b0c1a8` foi verificada à mão contra um banco
descartável (`syncchk_c4`, dropado ao final), e está registrada em
task-C4-report.md — não aqui. O que ESTE arquivo trava é o caminho que
aquela verificação nunca exercitou: as tabelas estavam vazias, então o
`upgrade()` passou pelo guard sem nunca levantar. Sem este teste, o ramo
"levanta quando há dado" desta revision ficaria sem cobertura nenhuma —
exatamente o gap que o fix round 1 da C3 fechou para a revision anterior.
"""

import importlib.util
from pathlib import Path

import pytest

_REVISION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "099099b0c1a8_orders_shipping_and_item_snapshot.py"
)


def _carregar_revision():
    """Carrega o módulo da revision pelo caminho — mesmo motivo do arquivo
    irmão (C3): `alembic/versions/` não é pacote importável, e carregar pelo
    arquivo mantém o teste amarrado à revision REAL."""
    spec = importlib.util.spec_from_file_location(
        "revision_orders_shipping_and_item_snapshot", _REVISION
    )
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class _FakeResult:
    def __init__(self, total: int) -> None:
        self._total = total

    def scalar_one(self) -> int:
        return self._total


class _FakeConn:
    """Conexão de mentira: devolve uma contagem pré-programada por consulta,
    e guarda o SQL recebido para o teste provar QUAIS tabelas foram
    consultadas, não só quantas."""

    def __init__(self, totais: list[int]) -> None:
        self._totais = list(totais)
        self.consultas: list[str] = []

    def execute(self, clause):
        self.consultas.append(str(clause))
        return _FakeResult(self._totais.pop(0))


def test_the_guard_allows_the_migration_through_when_every_table_is_empty():
    revision = _carregar_revision()
    conn = _FakeConn([0, 0])

    revision._falhar_se_houver_dado(conn)  # não deve levantar

    # As DUAS tabelas afetadas têm que ser consultadas — um guard que
    # checasse só uma deixaria a outra ser reescrita sem checagem.
    assert len(conn.consultas) == 2
    for tabela in ("orders", "order_items"):
        assert any(tabela in sql for sql in conn.consultas), tabela


def test_the_guard_raises_before_destroying_anything_when_a_table_has_rows():
    revision = _carregar_revision()
    # `orders` vazia, `order_items` com 3 linhas — o guard tem que acusar
    # `order_items` e parar aí, sem seguir para nenhum DDL.
    conn = _FakeConn([0, 3])

    with pytest.raises(RuntimeError) as erro:
        revision._falhar_se_houver_dado(conn)

    mensagem = str(erro.value)
    assert "order_items" in mensagem
    assert "3" in mensagem
    assert len(conn.consultas) == 2


def test_the_guard_covers_exactly_the_two_tables_the_migration_rewrites():
    """`_TABELAS_AFETADAS` e as tabelas que o `upgrade()` de fato reescreve
    têm que ser o mesmo conjunto. Se alguém acrescentar uma tabela à
    migration e esquecer do guard, ela passa a ser reescrita sem checagem."""
    revision = _carregar_revision()

    assert set(revision._TABELAS_AFETADAS) == {"orders", "order_items"}


def test_the_downgrade_refuses_instead_of_silently_restoring_an_empty_column():
    """`endereco_entrega` foi descartada por construção (drop_column). Um
    downgrade que recriasse a coluna vazia pareceria bem-sucedido mas
    devolveria um contrato sem o dado original — pior que recusar."""
    revision = _carregar_revision()

    with pytest.raises(RuntimeError, match="Sem downgrade"):
        revision.downgrade()
