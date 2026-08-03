from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subtema import Tema


async def buscar_tema_anterior(db: AsyncSession, tema_atual: Tema) -> Tema | None:
    """Tema imediatamente anterior na trilha da mesma matéria (pré-requisito)."""
    result = await db.execute(
        select(Tema)
        .where(Tema.materia_id == tema_atual.materia_id, Tema.ordem < tema_atual.ordem)
        .order_by(Tema.ordem.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def buscar_proximo_tema(db: AsyncSession, tema_atual: Tema) -> Tema | None:
    """Próximo tema na trilha da mesma matéria."""
    result = await db.execute(
        select(Tema)
        .where(Tema.materia_id == tema_atual.materia_id, Tema.ordem > tema_atual.ordem)
        .order_by(Tema.ordem.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()
