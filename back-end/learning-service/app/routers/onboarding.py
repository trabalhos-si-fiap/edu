from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.models.objetivo import ObjetivoAluno
from app.schemas.objetivo import ObjetivoIn, ObjetivoOut, ObjetivoSalvoOut
from app.services.roadmap import gerar_roadmap, prazo_apertado

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


async def _objetivo_do_aluno(db: AsyncSession, aluno_id: str) -> ObjetivoAluno | None:
    return (
        await db.execute(select(ObjetivoAluno).where(ObjetivoAluno.aluno_id == aluno_id))
    ).scalar_one_or_none()


@router.get("", response_model=ObjetivoOut | None)
async def ler_objetivo(
    aluno_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """O objetivo do aluno, ou `null`.

    `null` não é erro: aluno que pulou o onboarding é caso previsto, e um
    404 aqui faria a tela tratar "não preencheu ainda" como falha.
    """
    return await _objetivo_do_aluno(db, aluno_id)


@router.post("", response_model=ObjetivoSalvoOut, status_code=201)
async def criar_objetivo(
    payload: ObjetivoIn,
    aluno_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    hoje = date.today()
    objetivo = ObjetivoAluno(aluno_id=aluno_id, titulo=payload.titulo, data_alvo=payload.data_alvo)
    db.add(objetivo)
    try:
        await db.flush()
    except IntegrityError as exc:
        # `uq_objetivo_aluno`: dois POSTs simultâneos do mesmo aluno. O
        # segundo vira 409 em vez de 500 — e o cliente sabe que o caminho
        # certo é o PUT.
        await db.rollback()
        raise HTTPException(409, "Você já tem um objetivo. Altere o que existe.") from exc

    total = await gerar_roadmap(db, aluno_id=aluno_id, data_alvo=payload.data_alvo, hoje=hoje)
    await db.commit()
    await db.refresh(objetivo)
    return ObjetivoSalvoOut(
        objetivo=ObjetivoOut.model_validate(objetivo),
        etapas_geradas=total,
        prazo_apertado=prazo_apertado(total, hoje, payload.data_alvo),
    )


@router.put("", response_model=ObjetivoSalvoOut)
async def alterar_objetivo(
    payload: ObjetivoIn,
    aluno_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Altera o objetivo. Regenera o percurso SÓ quando a data muda.

    Mudar o título não move prazo nenhum: regenerar por causa de um texto
    apagaria e recriaria dezenas de linhas para um resultado idêntico.
    """
    objetivo = await _objetivo_do_aluno(db, aluno_id)
    if objetivo is None:
        raise HTTPException(404, "Você ainda não tem um objetivo")

    data_mudou = objetivo.data_alvo != payload.data_alvo
    objetivo.titulo = payload.titulo
    objetivo.data_alvo = payload.data_alvo

    hoje = date.today()
    if data_mudou:
        total = await gerar_roadmap(db, aluno_id=aluno_id, data_alvo=payload.data_alvo, hoje=hoje)
    else:
        total = await _contar_etapas(db, aluno_id)

    await db.commit()
    await db.refresh(objetivo)
    return ObjetivoSalvoOut(
        objetivo=ObjetivoOut.model_validate(objetivo),
        etapas_geradas=total,
        prazo_apertado=prazo_apertado(total, hoje, payload.data_alvo),
    )


async def _contar_etapas(db: AsyncSession, aluno_id: str) -> int:
    from sqlalchemy import func

    from app.models.roadmap import EtapaRoadmap

    total = await db.execute(
        select(func.count()).select_from(EtapaRoadmap).where(EtapaRoadmap.aluno_id == aluno_id)
    )
    return int(total.scalar_one())
