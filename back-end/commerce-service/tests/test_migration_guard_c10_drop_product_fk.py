"""Trava do guard de `downgrade()` da revision
`73f26f88d679_drop_order_items_product_fk` (task C10, fix round 1, Minor
promovido #5).

ESCOPO DESTE ARQUIVO — mesmo escopo declarado que os arquivos irmãos
(`test_migration_guard.py`, `test_migration_guard_c4.py`): exercita só a
lógica do guard, com uma conexão de mentira. NÃO roda a migration, NÃO toca
em banco nenhum.

Por que este guard existe: o `upgrade()` desta revision derruba a FK
`order_items.product_id -> products.id` de propósito — é a dívida de schema
#1 da task C10, para permitir apagar um produto referenciado por um pedido
histórico. Um `downgrade()` ingênuo que só recriasse a FK
(`op.create_foreign_key`) estouraria `ForeignKeyViolationError` cru do
Postgres exatamente no estado que a migration existe para permitir — uma
linha de `order_items` com `product_id` órfão. Achado da revisão: sem este
guard, esse erro cru (sem explicação) era a única coisa entre o operador e
uma tentativa de downgrade que não podia funcionar."""

import importlib.util
from pathlib import Path

import pytest

_REVISION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "73f26f88d679_drop_order_items_product_fk.py"
)


def _carregar_revision():
    spec = importlib.util.spec_from_file_location("revision_drop_order_items_product_fk", _REVISION)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class _FakeResult:
    def __init__(self, total: int) -> None:
        self._total = total

    def scalar_one(self) -> int:
        return self._total


class _FakeConn:
    def __init__(self, total: int) -> None:
        self._total = total
        self.consultas: list[str] = []

    def execute(self, clause):
        self.consultas.append(str(clause))
        return _FakeResult(self._total)


def test_the_guard_allows_downgrade_through_when_no_order_item_is_orphaned():
    revision = _carregar_revision()
    conn = _FakeConn(0)

    revision._falhar_se_downgrade_quebrar_referencia(conn)  # não deve levantar

    assert len(conn.consultas) == 1
    assert "order_items" in conn.consultas[0]
    assert "products" in conn.consultas[0]


def test_the_guard_raises_before_recreating_the_fk_when_a_row_is_orphaned():
    revision = _carregar_revision()
    conn = _FakeConn(3)

    with pytest.raises(RuntimeError) as erro:
        revision._falhar_se_downgrade_quebrar_referencia(conn)

    mensagem = str(erro.value)
    assert "3" in mensagem
    assert "order_items" in mensagem
