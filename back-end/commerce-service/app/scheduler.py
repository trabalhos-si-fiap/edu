"""Os dois jobs periódicos do commerce.

Mesmo padrão do `learning-service/app/scheduler.py`: um `AsyncIOScheduler`
global, ligado e desligado pelo `lifespan` do app.
"""

from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from app.config import settings
from app.database import async_session
from app.services.avanco_automatico import avancar_parados
from app.services.simulador_posicao import avancar_carregamentos

_scheduler: AsyncIOScheduler | None = None


async def tick_posicao() -> None:
    async with async_session() as db:
        await avancar_carregamentos(db, datetime.now(UTC))


async def tick_avanco_automatico() -> None:
    async with async_session() as db:
        await avancar_parados(db, datetime.now(UTC), settings.avanco_automatico_segundos)


def start_scheduler() -> None:
    global _scheduler
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(tick_posicao, "interval", seconds=settings.simulador_posicao_segundos)
    if settings.avanco_automatico_segundos > 0:
        # O job só é REGISTRADO quando o avanço está ligado. Registrar um job
        # que sempre devolve lista vazia gastaria uma conexão de banco por
        # minuto para não fazer nada, e esconderia no log a diferença entre
        # "ligado e nada a fazer" e "desligado".
        _scheduler.add_job(tick_avanco_automatico, "interval", seconds=60)
        logger.info(
            "scheduler: avanço automático LIGADO, prazo de {}s",
            settings.avanco_automatico_segundos,
        )
    else:
        logger.info("scheduler: avanço automático desligado (padrão)")
    _scheduler.start()


def stop_scheduler() -> None:
    if _scheduler:
        _scheduler.shutdown(wait=False)
