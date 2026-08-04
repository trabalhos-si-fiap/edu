from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.database import async_session
from app.events.publisher import publish_event
from app.models.progresso import AlunoTemaProgresso

_scheduler: AsyncIOScheduler | None = None


async def verificar_revisoes_pendentes() -> None:
    async with async_session() as db:
        agora = datetime.now(UTC)
        result = await db.execute(
            select(AlunoTemaProgresso).where(AlunoTemaProgresso.proxima_revisao <= agora)
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


def start_scheduler() -> None:
    global _scheduler
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(verificar_revisoes_pendentes, "cron", hour=6)  # roda 6h da manhã
    _scheduler.start()


def stop_scheduler() -> None:
    if _scheduler:
        _scheduler.shutdown(wait=False)
