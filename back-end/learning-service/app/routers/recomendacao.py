from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_student_id
from app.services.recomendacao import proximo_subtema
from app.services.recomendacao_semantica import subtemas_relacionados

router = APIRouter(prefix="/recomendacoes", tags=["recomendacao"])


@router.get("")
async def get_recomendacao(
    tema_id: int,
    aluno_id: str = Depends(get_current_student_id),
    db: AsyncSession = Depends(get_db),
):
    """Próximo subtema não dominado dentro do tema, seguindo a ordem curricular."""
    subtema = await proximo_subtema(db, aluno_id, tema_id)
    return subtema


@router.get("/relacionados/{subtema_id}")
async def get_subtemas_relacionados(
    subtema_id: int,
    k: int = 3,
    db: AsyncSession = Depends(get_db),
):
    """
    Sugere conteúdo relacionado por similaridade semântica (embeddings +
    scikit-learn NearestNeighbors), mesmo que esteja em outro tema/matéria
    — diferente de `GET /recomendacoes`, que segue só a ordem curricular
    dentro do mesmo tema.

    Diferente de `POST /diagnostico/responder` (onde essa mesma chamada é
    só um enriquecimento opcional e nunca derruba a resposta), aqui a
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
        {"subtema_id": sid, "nome": nome, "similaridade": sim} for sid, nome, sim in relacionados
    ]
