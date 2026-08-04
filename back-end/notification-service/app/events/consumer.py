"""Consumer de eventos do serviço — instância única sobre edu-common."""

import json

import aio_pika
from edu_common.events import EventConsumer, Handler

from app.config import settings
from app.database import async_session
from app.models.notificacao import Notificacao

# Mapa de subtema_id -> nome amigável para exibir na notificação.
# Pro MVP, um cache simples em memória evita chamar o Learning Service
# a cada evento; pode ser substituído por uma consulta real se preciso.
NOMES_SUBTEMA_FALLBACK = "seu conteúdo"

_consumer = EventConsumer(settings.rabbitmq_url, settings.exchange_name)


async def handle_revision_scheduled(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    async with message.process():
        payload = json.loads(message.body)
        async with async_session() as db:
            db.add(
                Notificacao(
                    aluno_id=payload["aluno_id"],
                    titulo="Hora de revisar!",
                    descricao=f"Você tem uma revisão agendada para {NOMES_SUBTEMA_FALLBACK}.",
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
        dominio = payload.get("dominio_tema")
        dominio_texto = f"{dominio:.0%}" if isinstance(dominio, int | float) else "não calculado"

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
    async with message.process():
        payload = json.loads(message.body)
        pedido_status = payload.get("status")

        mensagens = {
            "AGUARDANDO_SEPARACAO": "Seu pedido foi confirmado e entrará na fila de separação.",
            "EM_SEPARACAO": "Seu pedido está sendo separado no nosso centro de distribuição.",
            "SEPARADO": "Seu pedido foi separado e aguarda coleta.",
            "AGUARDANDO_COLETA": "Seu pedido está pronto para ser coletado pelo entregador.",
            "EM_TRANSITO": "Seu pedido saiu para entrega!",
            "ENTREGUE": "Seu pedido foi entregue. Bons estudos!",
            "CANCELADO": "Seu pedido foi cancelado.",
        }

        async with async_session() as db:
            db.add(
                Notificacao(
                    aluno_id=payload["aluno_id"],
                    titulo=f"Pedido #{payload['pedido_id']}",
                    descricao=mensagens.get(pedido_status, f"Status atualizado: {pedido_status}"),
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
                    titulo=f"Pedido #{payload['pedido_id']}: item em falta",
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
                    titulo=f"Pedido #{payload['pedido_id']}: atraso na entrega",
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


# Extraído do antigo `start_consumer` monolítico para constante de módulo —
# cada tupla é (nome da fila, routing key, handler). Cinco filas, uma
# routing key cada, todas ligadas à mesma exchange topic.
BINDINGS: list[tuple[str, str, Handler]] = [
    ("notification.revision_scheduled", "revision.scheduled", handle_revision_scheduled),
    ("notification.diagnostic_completed", "diagnostic.completed", handle_diagnostic_completed),
    ("notification.order_status_changed", "order.status_changed", handle_order_status_changed),
    ("notification.stock_issue", "order.stock_issue", handle_stock_issue),
    ("notification.delivery_delayed", "order.delivery_delayed", handle_delivery_delayed),
]


async def start_consumer() -> None:
    await _consumer.connect()
    for queue_name, routing_key, handler in BINDINGS:
        await _consumer.bind(queue_name, [routing_key], handler)


async def close_consumer() -> None:
    await _consumer.close()
