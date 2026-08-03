from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_student_id
from app.models.progresso import AlunoTemaProgresso
from app.models.subtema import Subtema
from app.schemas.revisao import RevisaoOut
from app.services.decisao import ClassificacaoSubtema, classificar_subtema

router = APIRouter(prefix="/revisoes", tags=["revisao"])


@router.get("/hoje", response_model=list[RevisaoOut])
async def revisoes_hoje(
    aluno_id: str = Depends(get_current_student_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AlunoTemaProgresso, Subtema)
        .join(Subtema, Subtema.id == AlunoTemaProgresso.subtema_id)
        .where(
            AlunoTemaProgresso.aluno_id == aluno_id,
            AlunoTemaProgresso.proxima_revisao <= datetime.now(UTC),
        )
        .order_by(AlunoTemaProgresso.proxima_revisao.asc())
    )

    revisoes = []
    for progresso, subtema in result.all():
        classificacao = classificar_subtema(progresso.nivel_dominio)
        video_url = (
            subtema.videoaula_base_url
            if classificacao == ClassificacaoSubtema.ESTUDAR_DO_ZERO
            else subtema.videoaula_revisao_url
        )
        revisoes.append(
            RevisaoOut(
                subtema_id=progresso.subtema_id,
                nome=subtema.nome,
                nivel_dominio=progresso.nivel_dominio,
                proxima_revisao=progresso.proxima_revisao,
                video_url=video_url,
            )
        )
    return revisoes
