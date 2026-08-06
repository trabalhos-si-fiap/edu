from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.questao import Questao
from app.models.subtema import Materia, Subtema, Tema
from app.schemas.materias import MateriaOut, SubtemaOut, TemaOut
from app.services.questionario import QUANTIDADE_PADRAO, montar_questionario

router = APIRouter(tags=["materias"])


@router.get("/subjects", response_model=list[MateriaOut])
async def listar_materias(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _usuario: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Materia).order_by(Materia.id.asc()).limit(limit).offset(offset)
    )
    return result.scalars().all()


@router.get("/subjects/{materia_id}/topics", response_model=list[TemaOut])
async def listar_temas(
    materia_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _usuario: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    materia = (
        await db.execute(select(Materia).where(Materia.id == materia_id))
    ).scalar_one_or_none()
    if not materia:
        raise HTTPException(404, "Matéria não encontrada")

    result = await db.execute(
        select(Tema)
        .where(Tema.materia_id == materia_id)
        # `.ordem` tem default=0 e não é única (models/subtema.py) — sem um
        # desempate por `.id`, linhas empatadas podem ser puladas ou
        # repetidas entre páginas de offset diferentes.
        .order_by(Tema.ordem.asc(), Tema.id.asc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.get("/topics/{tema_id}/subtopics", response_model=list[SubtemaOut])
async def listar_subtemas(
    tema_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _usuario: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tema = (await db.execute(select(Tema).where(Tema.id == tema_id))).scalar_one_or_none()
    if not tema:
        raise HTTPException(404, "Tema não encontrado")

    result = await db.execute(
        select(Subtema)
        .where(Subtema.tema_id == tema_id)
        # Mesma correção que em `listar_temas` acima: `.ordem` não é única.
        .order_by(Subtema.ordem.asc(), Subtema.id.asc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.get("/topics/{tema_id}/quiz")
async def gerar_questionario_diagnostico(
    tema_id: int,
    quantidade: int = Query(QUANTIDADE_PADRAO, ge=1, le=50),
    _usuario: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
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


@router.get("/subtopics/{subtema_id}/questions")
async def listar_questoes_diagnostico(
    subtema_id: int,
    limit: int = Query(8, ge=1, le=50),
    offset: int = Query(0, ge=0),
    _usuario: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Questionário focado em UM único subtema (ex: só "Membrana Plasmática"),
    útil para prática pontual — diferente de `/topics/{id}/quiz`, que cobre
    o tema inteiro. Não retorna o gabarito para o cliente.

    `order_by(Questao.id)` é obrigatório com `offset`: `Questao.id` é PK,
    então ordenar por ele já garante ordem total e estável — sem ele o
    Postgres não garante ordem alguma entre páginas, e a mesma questão
    pode aparecer nas duas, ou em nenhuma.
    """
    result = await db.execute(
        select(Questao)
        .where(Questao.subtema_id == subtema_id)
        .order_by(Questao.id)
        .limit(limit)
        .offset(offset)
    )
    questoes = result.scalars().all()
    # `offset > 0` e vazio quer dizer "página além do fim" de um subtema que
    # TEM questões — não "subtema sem conteúdo". Só o caso original
    # (offset=0, vazio de verdade) continua 404; passar do fim devolve lista
    # vazia com 200, como as outras listagens paginadas deste arquivo.
    if not questoes and offset == 0:
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
