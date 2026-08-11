import uuid

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.suporte import SupportMessage


async def listar_mensagens(db: AsyncSession, user_id: uuid.UUID) -> list[SupportMessage]:
    """A conversa do aluno, em ordem cronológica, INTEIRA — sem paginação.

    O filtro por `user_id` é a única defesa de posse que existe: `user_id` é
    FK lógica para outro banco, então nada no schema impede ler a conversa
    alheia — só esta cláusula.

    A ausência de paginação é uma exceção CONSCIENTE à regra 4 do
    `CLAUDE.md` (listagem sempre paginada), não um esquecimento: o critério
    de aceite deste bloco é a réplica exata do legacy
    (`legacy/app/modules/support/services.py`), que também devolve a conversa
    inteira. Paginar aqui divergiria do módulo que este serviço substitui.
    A conta que isso deixa em aberto — sem paginação, sem rate limit e sem
    teto por conversa, todo GET e todo POST materializam a thread completa —
    está registrada em `docs/back-end/phase-2-debt.md`.
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
