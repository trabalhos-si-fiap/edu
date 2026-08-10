"""Trava do guard de `downgrade()` da revision
`886205d547cc_notificacao_pedido_id_uuid` (task C10, fix round 1, Minor
promovido #5).

ESCOPO DESTE ARQUIVO: exercita só a lógica do guard, com uma conexão de
mentira. NÃO roda a migration, NÃO toca em banco nenhum.

Por que este guard existe: um UUID não tem correspondência com um inteiro
válido — não existe conversão de volta. `downgrade()`, sem guard, fazia
`ALTER ... TYPE integer USING NULL` incondicional: em qualquer banco que já
tivesse `pedido_id` preenchido de verdade (o objetivo desta migration
inteira é permitir isso), o downgrade descartaria todos esses valores em
silêncio — sem erro, sem aviso, só perda. Achado da revisão."""

import importlib.util
from pathlib import Path

import pytest

_REVISION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "886205d547cc_notificacao_pedido_id_uuid.py"
)


def _carregar_revision():
    spec = importlib.util.spec_from_file_location("revision_notificacao_pedido_id_uuid", _REVISION)
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


def test_the_guard_allows_downgrade_through_when_pedido_id_is_never_filled():
    revision = _carregar_revision()
    conn = _FakeConn(0)

    revision._falhar_se_pedido_id_tiver_dado(conn)  # não deve levantar

    assert len(conn.consultas) == 1
    assert "notificacoes" in conn.consultas[0]
    assert "pedido_id" in conn.consultas[0]


def test_the_guard_raises_before_discarding_a_filled_pedido_id():
    revision = _carregar_revision()
    conn = _FakeConn(5)

    with pytest.raises(RuntimeError) as erro:
        revision._falhar_se_pedido_id_tiver_dado(conn)

    mensagem = str(erro.value)
    assert "5" in mensagem
    assert "pedido_id" in mensagem
