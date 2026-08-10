"""Trava dos guards das DUAS direções da revision
`886205d547cc_notificacao_pedido_id_uuid` (task C10, fix round 1, Minor
promovido #5, e revisão final da branch).

ESCOPO DESTE ARQUIVO: exercita só a lógica dos guards, com uma conexão e um
`op` de mentira. NÃO roda a migration, NÃO toca em banco nenhum. A prova
contra Postgres de verdade (banco descartável, com linha e sem linha) está
no relatório da revisão final, não aqui.

Por que estes guards existem: `ALTER ... TYPE ... USING NULL` é
incondicional nas duas direções, e nenhuma delas tem conversão possível —
um inteiro não vira UUID nem um UUID vira inteiro. Sem guard, a migration
zera `pedido_id` em silêncio: sem erro, sem aviso, só perda.

O `downgrade()` já tinha guard desde a task C10. O `upgrade()` não tinha, e
ele é o único dos dois que roda no corte — o `notification_db` está vazio
hoje, mas o notification-service está no ar consumindo
`order.status_changed`, e "vazio hoje" não é "vazio no corte"."""

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


class _FakeOp:
    """`op` de mentira: registra na ordem o que a migration mandaria o
    Postgres fazer, para que um guard que roda DEPOIS do `ALTER` seja
    distinguível de um que roda antes."""

    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn
        self.operacoes: list[str] = []

    def get_bind(self) -> _FakeConn:
        return self._conn

    def f(self, nome: str) -> str:
        return nome

    def alter_column(self, *args, **kwargs) -> None:
        self.operacoes.append("alter_column")

    def create_index(self, *args, **kwargs) -> None:
        self.operacoes.append("create_index")

    def drop_index(self, *args, **kwargs) -> None:
        self.operacoes.append("drop_index")


def test_the_guard_allows_downgrade_through_when_pedido_id_is_never_filled():
    revision = _carregar_revision()
    conn = _FakeConn(0)

    revision._falhar_se_pedido_id_tiver_dado_no_downgrade(conn)  # não deve levantar

    assert len(conn.consultas) == 1
    assert "notificacoes" in conn.consultas[0]
    assert "pedido_id" in conn.consultas[0]


def test_the_guard_raises_before_discarding_a_filled_pedido_id():
    revision = _carregar_revision()
    conn = _FakeConn(5)

    with pytest.raises(RuntimeError) as erro:
        revision._falhar_se_pedido_id_tiver_dado_no_downgrade(conn)

    mensagem = str(erro.value)
    assert "5" in mensagem
    assert "pedido_id" in mensagem


def test_the_upgrade_refuses_to_null_a_filled_pedido_id(monkeypatch):
    """O `upgrade()` é o único dos dois que roda no corte — ele precisa do
    mesmo guard, e precisa rodá-lo ANTES do `ALTER`."""
    revision = _carregar_revision()
    conn = _FakeConn(3)
    fake_op = _FakeOp(conn)
    monkeypatch.setattr(revision, "op", fake_op)

    with pytest.raises(RuntimeError) as erro:
        revision.upgrade()

    assert fake_op.operacoes == []
    mensagem = str(erro.value)
    assert "3" in mensagem
    assert "pedido_id" in mensagem


def test_the_upgrade_goes_through_on_an_empty_table(monkeypatch):
    revision = _carregar_revision()
    conn = _FakeConn(0)
    fake_op = _FakeOp(conn)
    monkeypatch.setattr(revision, "op", fake_op)

    revision.upgrade()

    assert fake_op.operacoes == ["alter_column", "create_index"]
