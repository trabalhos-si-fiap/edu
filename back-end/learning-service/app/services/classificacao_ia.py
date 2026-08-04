"""
Classificação automática de texto (enunciado de questão) no subtema mais
semanticamente próximo, dentro de um tema — usado pela ingestão de
questões do ENEM (`scripts/ingest_enem.py`) para substituir o mapeamento
manual questão -> subtema que era necessário antes.
"""

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subtema import Subtema
from app.services.embeddings import gerar_embedding, gerar_embeddings, similaridade_cosseno

# Cache em memória dos embeddings de subtema, por tema_id. Simplificação de
# MVP: não invalida automaticamente se um subtema for editado/criado depois
# do primeiro uso no processo. Para produção real, valeria recalcular ao
# alterar `nome`/`descricao_ia`, ou usar um vector store dedicado (ex:
# FAISS, como já feito no Chatbot Service) em vez de um dict em memória.
_cache_embeddings_tema: dict[int, tuple[list[int], np.ndarray]] = {}


async def _embeddings_dos_subtemas(db: AsyncSession, tema_id: int):
    if tema_id in _cache_embeddings_tema:
        return _cache_embeddings_tema[tema_id]

    result = await db.execute(select(Subtema).where(Subtema.tema_id == tema_id))
    subtemas = result.scalars().all()

    # Combina nome + descricao_ia para dar mais sinal semântico ao modelo
    # do que só o nome curto do subtema forneceria sozinho.
    textos = [f"{s.nome}. {s.descricao_ia or ''}".strip() for s in subtemas]
    embeddings = gerar_embeddings(textos)
    ids = [s.id for s in subtemas]

    _cache_embeddings_tema[tema_id] = (ids, embeddings)
    return ids, embeddings


def invalidar_cache_tema(tema_id: int) -> None:
    """Chamar após editar/criar subtemas de um tema, para forçar recálculo
    dos embeddings na próxima classificação."""
    _cache_embeddings_tema.pop(tema_id, None)


async def classificar_texto_por_subtema(
    db: AsyncSession, tema_id: int, texto: str
) -> tuple[int | None, float]:
    """
    Classifica um texto (ex: enunciado de uma questão do ENEM) no subtema
    mais semanticamente próximo dentro de um tema, usando embeddings.

    Retorna (subtema_id, confianca). `confianca` é a similaridade de
    cosseno com o subtema mais próximo (na prática, entre ~0 e 1 para
    textos em português). Retorna (None, 0.0) se o tema não tiver nenhum
    subtema cadastrado.
    """
    ids, embeddings = await _embeddings_dos_subtemas(db, tema_id)
    if not ids:
        return None, 0.0

    embedding_texto = gerar_embedding(texto)
    similaridades = [similaridade_cosseno(embedding_texto, emb) for emb in embeddings]

    melhor_indice = max(range(len(similaridades)), key=lambda i: similaridades[i])
    return ids[melhor_indice], round(similaridades[melhor_indice], 3)
