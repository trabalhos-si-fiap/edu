import json
from contextlib import asynccontextmanager
from unittest.mock import MagicMock

from sqlalchemy import select

from app.events import consumer as consumer_module
from app.models.notificacao import Notificacao

STUDENT_ID = "00000000-0000-0000-0000-000000000001"


def fake_message(payload: dict) -> MagicMock:
    message = MagicMock()
    message.body = json.dumps(payload).encode()

    @asynccontextmanager
    async def process():
        yield

    message.process = process
    return message


def diagnostic_payload(acao: str, dominio_tema: float) -> dict:
    """A forma exata que `learning-service` publica em `diagnostic.completed`
    (`app/routers/diagnostico.py`): aluno_id, tema_id, dominio_tema, acao."""
    return {
        "aluno_id": STUDENT_ID,
        "tema_id": 12,
        "dominio_tema": dominio_tema,
        "acao": acao,
    }


async def test_diagnostic_completed_creates_a_notification(
    db_session, test_session_factory, monkeypatch
):
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_diagnostic_completed(
        fake_message(diagnostic_payload("avancar", 0.9))
    )

    stored = (await db_session.execute(select(Notificacao))).scalars().all()
    assert len(stored) == 1
    assert stored[0].tipo == "estudo"
    assert "avançar" in stored[0].descricao


async def test_diagnostic_retroceder_shows_the_real_dominio(
    db_session, test_session_factory, monkeypatch
):
    """`retroceder` é uma das três ações que o produtor emite. Sem entrada
    própria no dicionário ela caía no texto genérico, e como o handler lia a
    chave errada (`dominio`) o aluno via sempre "Domínio calculado: 0%",
    qualquer que fosse a nota real."""
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_diagnostic_completed(
        fake_message(diagnostic_payload("retroceder", 0.25))
    )

    stored = (await db_session.execute(select(Notificacao))).scalars().all()
    assert len(stored) == 1
    assert "25%" in stored[0].descricao
    assert "0%" not in stored[0].descricao


async def test_every_published_action_has_its_own_message(
    db_session, test_session_factory, monkeypatch
):
    """As três ações de `AcaoTema` — literais aqui de propósito, não
    importadas — precisam de mensagem própria; nenhuma pode cair no texto
    genérico de fallback."""
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    for acao in ("estudar", "avancar", "retroceder"):
        await consumer_module.handle_diagnostic_completed(
            fake_message(diagnostic_payload(acao, 0.5))
        )

    stored = (await db_session.execute(select(Notificacao))).scalars().all()
    assert len(stored) == 3
    for notificacao in stored:
        assert "Domínio calculado" not in notificacao.descricao


async def test_diagnostic_without_dominio_never_claims_zero_percent(
    db_session, test_session_factory, monkeypatch
):
    """Payload malformado não pode explodir dentro do handler nem inventar
    uma nota: o texto sai sem número, distinguível de um domínio real de 0%."""
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_diagnostic_completed(
        fake_message({"aluno_id": STUDENT_ID, "tema_id": 12, "acao": "retroceder"})
    )

    stored = (await db_session.execute(select(Notificacao))).scalars().all()
    assert len(stored) == 1
    assert "%" not in stored[0].descricao
    assert "não calculado" in stored[0].descricao


async def test_order_status_changed_creates_a_notification(
    db_session, test_session_factory, monkeypatch
):
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_order_status_changed(
        fake_message({"aluno_id": STUDENT_ID, "pedido_id": 7, "status": "EM_TRANSITO"})
    )

    stored = (await db_session.execute(select(Notificacao))).scalars().all()
    assert len(stored) == 1
    assert stored[0].pedido_id == 7
    assert "entrega" in stored[0].descricao.lower()


async def test_revision_scheduled_creates_a_notification(
    db_session, test_session_factory, monkeypatch
):
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_revision_scheduled(fake_message({"aluno_id": STUDENT_ID}))

    stored = (await db_session.execute(select(Notificacao))).scalars().all()
    assert len(stored) == 1
    assert stored[0].tipo == "estudo"
    assert str(stored[0].aluno_id) == STUDENT_ID


async def test_stock_issue_creates_a_notification_with_pedido_and_ocorrencia(
    db_session, test_session_factory, monkeypatch
):
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_stock_issue(
        fake_message(
            {
                "aluno_id": STUDENT_ID,
                "pedido_id": 3,
                "ocorrencia_id": 9,
                "produtos_sugeridos": [],
            }
        )
    )

    stored = (await db_session.execute(select(Notificacao))).scalars().all()
    assert len(stored) == 1
    assert stored[0].pedido_id == 3
    assert stored[0].ocorrencia_id == 9
    assert stored[0].tipo == "order_status"


async def test_delivery_delayed_creates_a_notification_with_pedido_and_ocorrencia(
    db_session, test_session_factory, monkeypatch
):
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_delivery_delayed(
        fake_message(
            {
                "aluno_id": STUDENT_ID,
                "pedido_id": 5,
                "ocorrencia_id": 11,
                "motivo": "Trânsito intenso",
            }
        )
    )

    stored = (await db_session.execute(select(Notificacao))).scalars().all()
    assert len(stored) == 1
    assert stored[0].pedido_id == 5
    assert stored[0].ocorrencia_id == 11
    assert "Trânsito intenso" in stored[0].descricao


async def test_every_binding_points_to_a_real_handler():
    """Compara `BINDINGS` contra o pareamento exato esperado — não só que
    cada handler é `callable`. `callable(handler)` sozinho passaria mesmo
    se duas entradas trocassem de handler entre si (ex.: `stock_issue`
    ligado ao handler de `delivery_delayed`), porque os testes que chamam
    cada handler diretamente (`test_diagnostic_completed_...` etc.) nunca
    passam por `BINDINGS` — nada mais nesta suíte pegaria essa troca."""
    expected = [
        (
            "notification.revision_scheduled",
            "revision.scheduled",
            consumer_module.handle_revision_scheduled,
        ),
        (
            "notification.diagnostic_completed",
            "diagnostic.completed",
            consumer_module.handle_diagnostic_completed,
        ),
        (
            "notification.order_status_changed",
            "order.status_changed",
            consumer_module.handle_order_status_changed,
        ),
        ("notification.stock_issue", "order.stock_issue", consumer_module.handle_stock_issue),
        (
            "notification.delivery_delayed",
            "order.delivery_delayed",
            consumer_module.handle_delivery_delayed,
        ),
    ]
    assert expected == consumer_module.BINDINGS
