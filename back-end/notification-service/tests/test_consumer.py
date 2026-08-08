import json
from contextlib import asynccontextmanager
from unittest.mock import MagicMock

from edu_common.contracts import DiagnosticCompleted
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
    """Construído pela MESMA definição que o produtor usa para publicar
    (`edu_common.contracts.DiagnosticCompleted`, montada em
    `learning-service/app/routers/diagnostico.py`) — não por um literal local.

    Era um literal, com uma docstring prometendo espelhar o produtor sem
    importar nada dele. A promessa era falsa e foi medida: renomear
    `dominio_tema` no produtor deixava esta suíte inteira verde (achado B8).
    Agora a renomeação chega até aqui pelo próprio payload — o handler
    continua lendo a chave que espera, não acha mais nada, e o texto da
    notificação muda. É isso que faz este teste falhar.
    """
    return DiagnosticCompleted(
        aluno_id=STUDENT_ID,
        tema_id=12,
        dominio_tema=dominio_tema,
        acao=acao,
    ).to_payload()


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
    """Um payload sem `dominio_tema` não pode inventar uma nota: o texto sai sem
    número, distinguível de um domínio real de 0%.

    O escopo é só a leitura de `dominio_tema` — é ela que tolera a chave
    ausente. O handler NÃO é imune a payload malformado em geral: ele ainda faz
    `payload["aluno_id"]`, que levanta `KeyError` se essa chave faltar. Esse
    comportamento é pré-existente e não está coberto aqui."""
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_diagnostic_completed(
        fake_message({"aluno_id": STUDENT_ID, "tema_id": 12, "acao": "retroceder"})
    )

    stored = (await db_session.execute(select(Notificacao))).scalars().all()
    assert len(stored) == 1
    assert "%" not in stored[0].descricao
    assert "não calculado" in stored[0].descricao


async def test_boolean_dominio_never_renders_as_a_percentage(
    db_session, test_session_factory, monkeypatch
):
    """`bool` é subtipo de `int` em Python, então `isinstance(True, int)` é
    verdadeiro e um `dominio_tema` booleano passaria pelo teste de tipo:
    `True` formataria como "100%" — dizendo a um aluno que está retrocedendo
    que ele dominou o tema — e `False` como "0%".

    Inalcançável pelo produtor de hoje (`calcular_dominio_tema` devolve
    `float`), então é seguro barato, não bug vivo: é a mesma classe do payload
    sem a chave, invertida — ali o risco era inventar 0%, aqui é inventar
    100%."""
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    for dominio in (True, False):
        await consumer_module.handle_diagnostic_completed(
            fake_message(
                {
                    "aluno_id": STUDENT_ID,
                    "tema_id": 12,
                    "dominio_tema": dominio,
                    "acao": "retroceder",
                }
            )
        )

    stored = (await db_session.execute(select(Notificacao))).scalars().all()
    assert len(stored) == 2
    for notificacao in stored:
        assert "%" not in notificacao.descricao
        assert "não calculado" in notificacao.descricao


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


async def test_order_status_changed_confirmado_creates_no_notification(
    db_session, test_session_factory, monkeypatch
):
    """CONFIRMADO é o estado que `confirmar_pagamento` (commerce-service)
    atravessa a caminho de AGUARDANDO_SEPARACAO na mesma chamada — nunca é
    um estado de repouso em operação normal. Sem esta supressão, o aluno
    receberia DUAS notificações por um único clique do admin, e a primeira
    leria o texto cru de fallback ("Status atualizado: CONFIRMADO") ao lado
    de sete vizinhas em português — porque `mensagens` não tem entrada
    própria para CONFIRMADO, de propósito (ver consumer.py)."""
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_order_status_changed(
        fake_message({"aluno_id": STUDENT_ID, "pedido_id": 7, "status": "CONFIRMADO"})
    )

    stored = (await db_session.execute(select(Notificacao))).scalars().all()
    assert len(stored) == 0


async def test_order_status_changed_aguardando_separacao_still_notifies(
    db_session, test_session_factory, monkeypatch
):
    """Guarda de regressão: a supressão de CONFIRMADO não pode se alargar e
    engolir o evento seguinte da mesma cadeia — AGUARDANDO_SEPARACAO
    continua criando exatamente uma notificação, com o texto de sempre."""
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_order_status_changed(
        fake_message({"aluno_id": STUDENT_ID, "pedido_id": 7, "status": "AGUARDANDO_SEPARACAO"})
    )

    stored = (await db_session.execute(select(Notificacao))).scalars().all()
    assert len(stored) == 1
    assert stored[0].descricao == "Seu pedido foi confirmado e entrará na fila de separação."


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


async def test_revision_notification_names_the_subtopic(
    db_session, test_session_factory, monkeypatch
):
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_revision_scheduled(
        fake_message(
            {
                "aluno_id": STUDENT_ID,
                "subtema_id": 7,
                "subtema_nome": "Membrana Plasmática",
                "proxima_revisao": "2026-08-10T06:00:00+00:00",
            }
        )
    )

    notificacao = (await db_session.execute(select(Notificacao))).scalar_one()
    assert "Membrana Plasmática" in notificacao.descricao


async def test_revision_notification_falls_back_when_the_name_is_missing(
    db_session, test_session_factory, monkeypatch
):
    """Payload antigo (sem `subtema_nome`) não pode derrubar o handler."""
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_revision_scheduled(
        fake_message(
            {
                "aluno_id": STUDENT_ID,
                "subtema_id": 7,
                "proxima_revisao": "2026-08-10T06:00:00+00:00",
            }
        )
    )

    notificacao = (await db_session.execute(select(Notificacao))).scalar_one()
    assert "seu conteúdo" in notificacao.descricao
