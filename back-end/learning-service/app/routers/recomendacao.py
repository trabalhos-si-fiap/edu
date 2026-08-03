from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_student_id, get_current_user
from app.schemas.diagnostico import SubtemaRelacionadoOut
from app.schemas.recomendacao import SubtemaRecomendadoOut
from app.services.recomendacao import proximo_subtema
from app.services.recomendacao_semantica import subtemas_relacionados

router = APIRouter(prefix="/recommendations", tags=["recomendacao"])


@router.get("", response_model=SubtemaRecomendadoOut | None)
async def get_recomendacao(
    tema_id: int,
    aluno_id: str = Depends(get_current_student_id),
    db: AsyncSession = Depends(get_db),
):
    """Próximo subtema não dominado dentro do tema, seguindo a ordem curricular."""
    subtema = await proximo_subtema(db, aluno_id, tema_id)
    if subtema is None:
        return None

    return SubtemaRecomendadoOut(
        id=subtema.id,
        tema_id=subtema.tema_id,
        nome=subtema.nome,
        ordem=subtema.ordem,
        videoaula_base_url=subtema.videoaula_base_url,
        videoaula_revisao_url=subtema.videoaula_revisao_url,
    )


@router.get("/related/{subtema_id}", response_model=list[SubtemaRelacionadoOut])
async def get_subtemas_relacionados(
    subtema_id: int,
    k: int = 3,
    _usuario: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Sugere conteúdo relacionado por similaridade semântica (embeddings +
    scikit-learn NearestNeighbors), mesmo que esteja em outro tema/matéria
    — diferente de `GET /recommendations`, que segue só a ordem curricular
    dentro do mesmo tema.

    Diferente de `POST /diagnostic/answer` (onde essa mesma chamada é só
    um enriquecimento opcional e nunca derruba a resposta), aqui a
    similaridade semântica É o propósito do endpoint — se o modelo de
    embeddings falhar (sem internet, timeout etc.), retorna 503 explicando
    o motivo em vez de vazar um stack trace bruto ao cliente.
    """
    try:
        relacionados = await subtemas_relacionados(db, subtema_id, k=k)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Serviço de recomendação por IA temporariamente indisponível.",
        ) from exc

    return [
        SubtemaRelacionadoOut(subtema_id=sid, nome=nome, similaridade=sim)
        for sid, nome, sim in relacionados
    ]
