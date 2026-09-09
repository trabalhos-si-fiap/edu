"""Consumer de eventos do serviço — instância única sobre edu-common."""

import json

import aio_pika
from edu_common.events import EventConsumer, Handler
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.database import async_session
from app.models.notificacao import Notificacao
from app.models.staff import Staff
from app.services.destinatarios import (
    ALUNO,
    PAPEIS_OCCURRENCE_RESOLVED,
    PAPEIS_ORDER_CREATED,
    PAPEIS_POR_STATUS,
    resolver,
)

# O produtor (`learning-service/app/scheduler.py`) manda `subtema_nome` no
# payload desde a fase 2 — este serviço não tem banco de conteúdo e não pode
# resolver o id sozinho. O fallback cobre mensagem antiga ainda na fila no
# momento do deploy; sem ele, um `KeyError` derrubaria o handler e a
# mensagem sumiria (não há DLQ até a fase 3).
NOMES_SUBTEMA_FALLBACK = "seu conteúdo"

_consumer = EventConsumer(settings.rabbitmq_url, settings.exchange_name)


def _id_curto(pedido_id: str) -> str:
    """Mesma regra do `idCurto` do app (order.dart:146): 8 primeiros
    caracteres em maiúsculas.

    `pedido_id` virou UUID na fase 2 e os títulos passaram a mostrar 36
    caracteres hexadecimais. Truncar aqui, com a MESMA regra do cliente,
    mantém push e tela exibindo o mesmo identificador.
    """
    return pedido_id[:8].upper() if len(pedido_id) > 8 else pedido_id.upper()


async def handle_revision_scheduled(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    async with message.process():
        payload = json.loads(message.body)
        subtema_nome = payload.get("subtema_nome") or NOMES_SUBTEMA_FALLBACK
        async with async_session() as db:
            db.add(
                Notificacao(
                    aluno_id=payload["aluno_id"],
                    titulo="Hora de revisar!",
                    descricao=f"Você tem uma revisão agendada para {subtema_nome}.",
                    tipo="estudo",
                )
            )
            await db.commit()


async def handle_diagnostic_completed(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    async with message.process():
        payload = json.loads(message.body)
        acao = payload.get("acao")
        # `dominio_tema` é a chave que o Learning Service publica de fato
        # (0.0 a 1.0). Sem default numérico de propósito: com `.get("...", 0)`
        # um payload malformado renderizaria "0%" — indistinguível de um
        # aluno que realmente zerou. Aqui ele vira um texto sem número.
        # `bool` é subtipo de `int`, então `isinstance(True, int)` passaria e
        # renderizaria "100%" para um aluno que está retrocedendo (e "0%" para
        # `False`). O produtor de hoje só publica `float`, mas o custo de
        # excluir o bool aqui é uma cláusula.
        dominio = payload.get("dominio_tema")
        dominio_valido = isinstance(dominio, int | float) and not isinstance(dominio, bool)
        dominio_texto = f"{dominio:.0%}" if dominio_valido else "não calculado"

        # Uma entrada por ação que o produtor emite — `AcaoTema` tem
        # exatamente estas três (learning-service/app/services/decisao.py).
        mensagens = {
            "estudar": "Identificamos uma lacuna nesse conteúdo. Vamos começar do zero!",
            "avancar": "Conteúdo dominado! Você já pode avançar para o próximo tema.",
            "retroceder": (
                f"Seu domínio ficou em {dominio_texto} nesse tema. Vamos reforçar a base "
                "no tema anterior antes de seguir — você chega lá!"
            ),
        }

        async with async_session() as db:
            db.add(
                Notificacao(
                    aluno_id=payload["aluno_id"],
                    titulo="Resultado do diagnóstico",
                    descricao=mensagens.get(acao, f"Domínio calculado: {dominio_texto}"),
                    tipo="estudo",
                )
            )
            await db.commit()


async def handle_order_status_changed(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    # CONFIRMADO não gera notificação, de propósito: é um estado transitório
    # que `confirmar_pagamento` (commerce-service) atravessa direto para
    # AGUARDANDO_SEPARACAO, na MESMA chamada — nunca é um estado de repouso
    # em operação normal. Sem esta supressão o aluno receberia duas
    # notificações por um único clique do admin, e a mensagem de
    # AGUARDANDO_SEPARACAO ("Seu pedido foi confirmado e entrará na fila de
    # separação.") já diz o que uma mensagem de CONFIRMADO diria — a segunda
    # seria sempre uma duplicata publicada milissegundos depois da primeira.
    # O evento em si continua sendo publicado e consumido normalmente
    # (analytics-service e o status-history do commerce-service dependem
    # dele) — só a notificação é suprimida, e agora como consequência da
    # tabela de destinatário (`PAPEIS_POR_STATUS["CONFIRMADO"]` é a tupla
    # vazia), não mais de um `return` antecipado aqui.
    async with message.process():
        payload = json.loads(message.body)
        pedido_status = payload.get("status")

        mensagens = {
            "AGUARDANDO_SEPARACAO": "Seu pedido foi confirmado e entrará na fila de separação.",
            "EM_SEPARACAO": "Seu pedido está sendo separado no nosso centro de distribuição.",
            "AGUARDANDO_SUBSTITUICAO": (
                "Um item do seu pedido está em falta. Toque para escolher um "
                "substituto ou cancelar."
            ),
            "SEPARADO": "Seu pedido foi separado e aguarda coleta.",
            "AGUARDANDO_COLETA": "Seu pedido está pronto para ser coletado pelo entregador.",
            "EM_TRANSITO": "Seu pedido saiu para entrega!",
            "ENTREGUE": "Seu pedido foi entregue. Bons estudos!",
            "CANCELADO": "Seu pedido foi cancelado.",
        }

        async with async_session() as db:
            # Estado desconhecido (nenhuma entrada em `PAPEIS_POR_STATUS`) cai
            # no fallback `(ALUNO,)` — o comprador continua sendo avisado
            # mesmo de uma transição que este dicionário ainda não conhece;
            # é `test_every_internal_status_has_a_recipient_rule` quem garante
            # que os dez estados internos do commerce não dependem desse
            # fallback.
            papeis = PAPEIS_POR_STATUS.get(pedido_status, (ALUNO,))
            destinatarios = await resolver(db, papeis, payload["aluno_id"])
            for destinatario_id in destinatarios:
                db.add(
                    Notificacao(
                        aluno_id=destinatario_id,
                        titulo=f"Pedido #{_id_curto(payload['pedido_id'])}",
                        descricao=mensagens.get(
                            pedido_status, f"Status atualizado: {pedido_status}"
                        ),
                        tipo="order_status",
                        pedido_id=payload["pedido_id"],
                    )
                )
            await db.commit()


async def handle_stock_issue(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    async with message.process():
        payload = json.loads(message.body)
        tem_sugestoes = bool(payload.get("produtos_sugeridos"))

        descricao = (
            "Um item do seu pedido está em falta. Encontramos produtos "
            "similares — toque para escolher um substituto ou cancelar o item."
            if tem_sugestoes
            else "Um item do seu pedido está em falta. Toque para decidir como prosseguir."
        )

        async with async_session() as db:
            db.add(
                Notificacao(
                    aluno_id=payload["aluno_id"],
                    titulo=f"Pedido #{_id_curto(payload['pedido_id'])}: item em falta",
                    descricao=descricao,
                    tipo="order_status",
                    pedido_id=payload["pedido_id"],
                    ocorrencia_id=payload["ocorrencia_id"],
                )
            )
            await db.commit()


async def handle_delivery_delayed(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    async with message.process():
        payload = json.loads(message.body)
        async with async_session() as db:
            db.add(
                Notificacao(
                    aluno_id=payload["aluno_id"],
                    titulo=f"Pedido #{_id_curto(payload['pedido_id'])}: atraso na entrega",
                    descricao=(
                        f"{payload.get('motivo', 'Houve um imprevisto na entrega')}. "
                        "Toque para aceitar a nova data ou cancelar o pedido."
                    ),
                    tipo="order_status",
                    pedido_id=payload["pedido_id"],
                    ocorrencia_id=payload["ocorrencia_id"],
                )
            )
            await db.commit()


async def handle_staff_created(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    """Réplica local de quem é staff, alimentada pelo evento que
    `auth-users-service` já publica (ver `Staff`, D6 do plano da spec C).

    `ON CONFLICT DO NOTHING` sobre `user_id` (PK) torna o registro idempotente
    de forma atômica — a fila é durável e a entrega é ao-menos-uma-vez, então
    a mesma mensagem pode chegar duas vezes depois de um restart do broker.
    Mesmo idioma de `registrar_device` (`app/routers/notificacoes.py`), e pelo
    mesmo motivo: nenhuma janela de corrida entre um SELECT e o INSERT.
    """
    async with message.process():
        payload = json.loads(message.body)
        async with async_session() as db:
            stmt = (
                pg_insert(Staff)
                .values(
                    user_id=payload["user_id"],
                    papel=payload["role"],
                    nome=payload["nome"],
                )
                .on_conflict_do_nothing(index_elements=["user_id"])
            )
            await db.execute(stmt)
            await db.commit()


async def handle_order_created(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    """`order.created` era publicado e ninguém consumia. Quem precisa saber
    que entrou pedido é a operação (admin, separador) — não o aluno, que
    acabou de clicar em comprar."""
    async with message.process():
        payload = json.loads(message.body)
        async with async_session() as db:
            destinatarios = await resolver(db, PAPEIS_ORDER_CREATED, payload["aluno_id"])
            for destinatario_id in destinatarios:
                db.add(
                    Notificacao(
                        aluno_id=destinatario_id,
                        titulo=f"Pedido #{_id_curto(payload['pedido_id'])}",
                        descricao="Um pedido novo entrou na fila.",
                        tipo="order_status",
                        pedido_id=payload["pedido_id"],
                    )
                )
            await db.commit()


async def handle_occurrence_resolved(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    """`order.occurrence_resolved` é publicado desde a fase 2 e não tinha
    consumidor neste serviço. É o separador quem está bloqueado esperando a
    decisão do aluno — `finalizar_separacao` (commerce-service) recusa
    finalizar com ocorrência aberta."""
    async with message.process():
        payload = json.loads(message.body)
        resolucao = payload.get("resolucao")
        mensagens = {
            "substituir": "O aluno escolheu um substituto para o item em falta.",
            "remover_item": "O aluno optou por remover o item em falta do pedido.",
            "cancelar_pedido": "O aluno cancelou o pedido.",
        }
        descricao = mensagens.get(resolucao, f"Ocorrência resolvida: {resolucao}.")

        async with async_session() as db:
            destinatarios = await resolver(db, PAPEIS_OCCURRENCE_RESOLVED, payload["aluno_id"])
            for destinatario_id in destinatarios:
                db.add(
                    Notificacao(
                        aluno_id=destinatario_id,
                        titulo=f"Pedido #{_id_curto(payload['pedido_id'])}: ocorrência resolvida",
                        descricao=f"{descricao} Pode prosseguir com a separação.",
                        tipo="order_status",
                        pedido_id=payload["pedido_id"],
                        ocorrencia_id=payload.get("ocorrencia_id"),
                    )
                )
            await db.commit()


# Extraído do antigo `start_consumer` monolítico para constante de módulo —
# cada tupla é (nome da fila, routing key, handler). Oito filas, uma
# routing key cada, todas ligadas à mesma exchange topic.
BINDINGS: list[tuple[str, str, Handler]] = [
    ("notification.revision_scheduled", "revision.scheduled", handle_revision_scheduled),
    ("notification.diagnostic_completed", "diagnostic.completed", handle_diagnostic_completed),
    ("notification.order_status_changed", "order.status_changed", handle_order_status_changed),
    ("notification.stock_issue", "order.stock_issue", handle_stock_issue),
    ("notification.delivery_delayed", "order.delivery_delayed", handle_delivery_delayed),
    ("notification.staff_created", "staff.created", handle_staff_created),
    ("notification.order_created", "order.created", handle_order_created),
    (
        "notification.occurrence_resolved",
        "order.occurrence_resolved",
        handle_occurrence_resolved,
    ),
]


async def start_consumer() -> None:
    await _consumer.connect()
    for queue_name, routing_key, handler in BINDINGS:
        await _consumer.bind(queue_name, [routing_key], handler)


async def close_consumer() -> None:
    await _consumer.close()
