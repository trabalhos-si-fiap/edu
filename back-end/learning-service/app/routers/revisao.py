from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.models.progresso import AlunoTemaProgresso
from app.models.subtema import Subtema
from app.schemas.revisao import RevisaoOut
from app.services.decisao import ClassificacaoSubtema, classificar_subtema

router = APIRouter(prefix="/reviews", tags=["revisao"])


@router.get("/today", response_model=list[RevisaoOut])
async def revisoes_hoje(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    aluno_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AlunoTemaProgresso, Subtema)
        .join(Subtema, Subtema.id == AlunoTemaProgresso.subtema_id)
        .where(
            AlunoTemaProgresso.aluno_id == aluno_id,
            AlunoTemaProgresso.proxima_revisao <= datetime.now(UTC),
        )
        # `.proxima_revisao` sozinho não é único (dois subtemas podem cair
        # devidos no mesmo instante) — `.id` como desempate garante uma
        # ordem total estável entre páginas (mesma correção do MINOR 5
        # em materias.py: `.ordem` também não é única lá).
        .order_by(AlunoTemaProgresso.proxima_revisao.asc(), AlunoTemaProgresso.id.asc())
        .limit(limit)
        .offset(offset)
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
