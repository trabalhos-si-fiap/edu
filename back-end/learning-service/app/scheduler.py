from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import or_, select

from app.database import async_session
from app.events.publisher import publish_event
from app.models.progresso import AlunoTemaProgresso

_scheduler: AsyncIOScheduler | None = None


async def verificar_revisoes_pendentes() -> None:
    async with async_session() as db:
        agora = datetime.now(UTC)
        # `ultima_revisao >= proxima_revisao` significa "esta data de revisão
        # já virou notificação". Sem essa cláusula o job republicava a MESMA
        # linha toda manhã, para sempre: nada aqui escrevia de volta, e a
        # coluna `ultima_revisao` (que existe no model desde a importação)
        # nunca era usada por ninguém.
        #
        # Quando o aluno responde de novo, `/diagnostic/answer` grava um
        # `proxima_revisao` no futuro, que passa a ser maior que
        # `ultima_revisao` — e a linha volta a ficar elegível sozinha, sem
        # precisar de reset.
        result = await db.execute(
            select(AlunoTemaProgresso).where(
                AlunoTemaProgresso.proxima_revisao <= agora,
                or_(
                    AlunoTemaProgresso.ultima_revisao.is_(None),
                    AlunoTemaProgresso.ultima_revisao < AlunoTemaProgresso.proxima_revisao,
                ),
            )
        )
        pendentes = result.scalars().all()

        for item in pendentes:
            await publish_event(
                "revision.scheduled",
                {
                    "aluno_id": str(item.aluno_id),
                    "subtema_id": item.subtema_id,
                    "proxima_revisao": item.proxima_revisao.isoformat(),
                },
            )
            # Depois do publish de propósito: se ele estourar, o commit não
            # acontece e a revisão continua pendente para a próxima passada.
            # Entrega ao menos uma vez é o comportamento certo aqui — marcar
            # antes perderia a notificação em silêncio.
            item.ultima_revisao = agora

        await db.commit()


def start_scheduler() -> None:
    global _scheduler
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(verificar_revisoes_pendentes, "cron", hour=6)  # roda 6h da manhã
    _scheduler.start()


def stop_scheduler() -> None:
    if _scheduler:
        _scheduler.shutdown(wait=False)
