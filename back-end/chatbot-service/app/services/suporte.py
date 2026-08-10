import uuid

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.suporte import SupportMessage


async def listar_mensagens(db: AsyncSession, user_id: uuid.UUID) -> list[SupportMessage]:
    """A conversa do aluno, em ordem cronológica.

    O filtro por `user_id` é a única defesa de posse que existe: `user_id` é
    FK lógica para outro banco, então nada no schema impede ler a conversa
    alheia — só esta cláusula.
    """
    stmt = (
        select(SupportMessage)
        .where(SupportMessage.user_id == user_id)
        .order_by(SupportMessage.created_at)
    )
    return list((await db.execute(stmt)).scalars().all())


async def enviar_mensagem(db: AsyncSession, user_id: uuid.UUID, body: str) -> list[SupportMessage]:
    """Grava a mensagem e devolve a conversa COMPLETA.

    Devolver a lista inteira, e não só a mensagem criada, é o contrato: o app
    substitui a conversa pela resposta do POST em vez de acrescentar
    localmente, então uma resposta parcial esvaziaria a tela.
    """
    mensagem = SupportMessage(user_id=user_id, sender="user", body=body)
    db.add(mensagem)
    await db.commit()
    logger.info("support: mensagem enviada id={} user={}", mensagem.id, user_id)
    return await listar_mensagens(db, user_id)
