from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.progresso import AlunoTemaProgresso
from app.models.subtema import Subtema
from app.services.decisao import LIMIAR_DOMINIO_SUBTEMA


async def proximo_subtema(db: AsyncSession, aluno_id: str, tema_id: int) -> Subtema | None:
    """
    Retorna o próximo subtema não dominado, seguindo a ordem curricular
    (grafo de pré-requisitos simplificado pela coluna `ordem`).
    Ponto de extensão para v2: trocar por scikit-learn NearestNeighbors
    comparando o vetor de lacunas do aluno com o conteúdo disponível.
    """
    result = await db.execute(
        select(Subtema)
        .outerjoin(
            AlunoTemaProgresso,
            (AlunoTemaProgresso.subtema_id == Subtema.id)
            & (AlunoTemaProgresso.aluno_id == aluno_id),
        )
        .where(Subtema.tema_id == tema_id)
        .where(
            (AlunoTemaProgresso.nivel_dominio.is_(None))
            | (AlunoTemaProgresso.nivel_dominio < LIMIAR_DOMINIO_SUBTEMA)
        )
        .order_by(Subtema.ordem.asc())
    )
    return result.scalars().first()
