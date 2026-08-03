from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.questao import Questao
from app.models.subtema import Materia, Subtema, Tema
from app.services.questionario import QUANTIDADE_PADRAO, montar_questionario

router = APIRouter(tags=["materias"])


@router.get("/materias")
async def listar_materias(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Materia))
    return result.scalars().all()


@router.get("/materias/{materia_id}/temas")
async def listar_temas(materia_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Tema).where(Tema.materia_id == materia_id).order_by(Tema.ordem.asc())
    )
    return result.scalars().all()


@router.get("/temas/{tema_id}/subtemas")
async def listar_subtemas(tema_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Subtema).where(Subtema.tema_id == tema_id).order_by(Subtema.ordem.asc())
    )
    return result.scalars().all()


@router.get("/temas/{tema_id}/questionario")
async def gerar_questionario_diagnostico(
    tema_id: int, quantidade: int = QUANTIDADE_PADRAO, db: AsyncSession = Depends(get_db)
):
    """
    Monta o questionário de diagnóstico do tema inteiro (ex: Citologia),
    distribuindo as questões entre todos os seus subtemas (Membrana,
    Organelas, Metabolismo, Núcleo...). Não retorna o gabarito.
    """
    questoes = await montar_questionario(db, tema_id, quantidade)
    if not questoes:
        raise HTTPException(404, "Nenhuma questão encontrada para este tema")

    return [
        {
            "id": q.id,
            "subtema_id": q.subtema_id,
            "enunciado": q.enunciado,
            "alternativas": q.alternativas,
            "nivel_dificuldade": q.nivel_dificuldade,
        }
        for q in questoes
    ]


@router.get("/subtemas/{subtema_id}/questoes")
async def listar_questoes_diagnostico(
    subtema_id: int, limite: int = 8, db: AsyncSession = Depends(get_db)
):
    """
    Questionário focado em UM único subtema (ex: só "Membrana Plasmática"),
    útil para prática pontual — diferente de `/temas/{id}/questionario`,
    que cobre o tema inteiro. Não retorna o gabarito para o cliente.
    """
    result = await db.execute(select(Questao).where(Questao.subtema_id == subtema_id).limit(limite))
    questoes = result.scalars().all()
    if not questoes:
        raise HTTPException(404, "Nenhuma questão encontrada para este subtema")

    return [
        {
            "id": q.id,
            "enunciado": q.enunciado,
            "alternativas": q.alternativas,
            "nivel_dificuldade": q.nivel_dificuldade,
        }
        for q in questoes
    ]
