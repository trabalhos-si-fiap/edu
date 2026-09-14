from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.models.objetivo import ObjetivoAluno
from app.models.progresso import AlunoTemaProgresso
from app.models.roadmap import EtapaRoadmap
from app.schemas.perfil import (
    EstudoResumoOut,
    ObjetivoResumoOut,
    PontosResumoOut,
    ResumoOut,
    RoadmapResumoOut,
)
from app.services.pontuacao import nivel_do_total, total_de_pontos

router = APIRouter(prefix="/profile", tags=["perfil"])


@router.get("/summary", response_model=ResumoOut)
async def resumo(
    aluno_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Tudo que a tela inicial e o perfil precisam, numa chamada.

    Cada campo tem origem única e verificável — nenhum é derivado de outro
    campo desta mesma resposta.
    """
    objetivo = (
        await db.execute(select(ObjetivoAluno).where(ObjetivoAluno.aluno_id == aluno_id))
    ).scalar_one_or_none()

    objetivo_out = None
    if objetivo is not None:
        inicio = objetivo.criado_em.date()
        dias_totais = max((objetivo.data_alvo - inicio).days, 0)
        # `min` com o total: um objetivo cuja data já passou mostra o
        # percurso cheio. Sem isso a barra da tela passaria de 100%.
        dias_decorridos = max(min((date.today() - inicio).days, dias_totais), 0)
        objetivo_out = ObjetivoResumoOut(
            titulo=objetivo.titulo,
            data_alvo=objetivo.data_alvo,
            dias_decorridos=dias_decorridos,
            dias_totais=dias_totais,
        )

    etapas_totais, etapas_concluidas = (
        await db.execute(
            select(
                func.count(),
                func.count(EtapaRoadmap.concluida_em),
            ).where(EtapaRoadmap.aluno_id == aluno_id)
        )
    ).one()

    total_pontos = await total_de_pontos(db, aluno_id)

    streak, respondidas, iniciados = (
        await db.execute(
            select(
                func.coalesce(func.max(AlunoTemaProgresso.streak_acertos), 0),
                func.coalesce(func.sum(AlunoTemaProgresso.total_respondidas), 0),
                # `student.created` já cria uma linha zerada por subtema:
                # iniciado é quem tem resposta, não quem tem linha.
                func.count().filter(AlunoTemaProgresso.total_respondidas > 0),
            ).where(AlunoTemaProgresso.aluno_id == aluno_id)
        )
    ).one()

    return ResumoOut(
        objetivo=objetivo_out,
        roadmap=RoadmapResumoOut(
            etapas_totais=int(etapas_totais),
            etapas_concluidas=int(etapas_concluidas),
            progresso=(round(etapas_concluidas / etapas_totais, 4) if etapas_totais else 0.0),
        ),
        pontos=PontosResumoOut(
            total=total_pontos,
            nivel=nivel_do_total(total_pontos),
            streak=int(streak),
        ),
        estudo=EstudoResumoOut(
            questoes_respondidas=int(respondidas),
            subtemas_iniciados=int(iniciados),
        ),
    )
