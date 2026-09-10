from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.models.objetivo import ObjetivoAluno
from app.models.questao import Questao
from app.models.roadmap import EtapaRoadmap
from app.models.subtema import Materia, Subtema, Tema
from app.schemas.objetivo import ObjetivoOut
from app.schemas.roadmap import EtapaOut, RoadmapOut
from app.services.roadmap import prazo_apertado

router = APIRouter(prefix="/roadmap", tags=["roadmap"])

SEM_OBJETIVO = "Defina um objetivo e uma data-alvo para montar seu percurso."


@router.get("", response_model=RoadmapOut)
async def listar_roadmap(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    aluno_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    objetivo = (
        await db.execute(select(ObjetivoAluno).where(ObjetivoAluno.aluno_id == aluno_id))
    ).scalar_one_or_none()
    if objetivo is None:
        return RoadmapOut(
            objetivo=None,
            motivo=SEM_OBJETIVO,
            prazo_apertado=False,
            items=[],
            total=0,
            limit=limit,
            offset=offset,
        )

    total = int(
        (
            await db.execute(
                select(func.count())
                .select_from(EtapaRoadmap)
                .where(EtapaRoadmap.aluno_id == aluno_id)
            )
        ).scalar_one()
    )

    linhas = (
        await db.execute(
            select(EtapaRoadmap, Subtema, Tema, Materia)
            .join(Subtema, Subtema.id == EtapaRoadmap.subtema_id)
            .join(Tema, Tema.id == Subtema.tema_id)
            .join(Materia, Materia.id == Tema.materia_id)
            .where(EtapaRoadmap.aluno_id == aluno_id)
            # `.ordem` é única por aluno na prática, mas `.id` como desempate
            # mantém a ordem total estável entre páginas mesmo se uma
            # regeneração concorrente empatar dois valores.
            .order_by(EtapaRoadmap.ordem.asc(), EtapaRoadmap.id.asc())
            .limit(limit)
            .offset(offset)
        )
    ).all()

    # UMA agregação para todas as etapas da página, não uma consulta por
    # etapa: com 130 subtemas no seed do ENEM, o caminho ingênuo seriam 130
    # viagens ao banco para desenhar uma tela.
    ids_da_pagina = [etapa.subtema_id for etapa, _s, _t, _m in linhas]
    com_questao: set[int] = set()
    if ids_da_pagina:
        com_questao = set(
            (
                await db.execute(
                    select(Questao.subtema_id)
                    .where(Questao.subtema_id.in_(ids_da_pagina))
                    .group_by(Questao.subtema_id)
                )
            )
            .scalars()
            .all()
        )

    items = [
        EtapaOut(
            subtema_id=etapa.subtema_id,
            subtema_nome=subtema.nome,
            tema_id=tema.id,
            tema_nome=tema.nome,
            materia_nome=materia.nome,
            ordem=etapa.ordem,
            prazo=etapa.prazo,
            concluida=etapa.concluida_em is not None,
            concluida_em=etapa.concluida_em,
            tem_questoes=etapa.subtema_id in com_questao,
        )
        for etapa, subtema, tema, materia in linhas
    ]

    return RoadmapOut(
        objetivo=ObjetivoOut.model_validate(objetivo),
        motivo=None,
        prazo_apertado=prazo_apertado(total, date.today(), objetivo.data_alvo),
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
