"""
Recomendação de conteúdo relacionado por similaridade semântica, usando
scikit-learn NearestNeighbors sobre embeddings de TODOS os subtemas
cadastrados (cruzando temas e matérias).

Este módulo implementa o ponto de extensão que já estava sinalizado desde
o início do projeto em `recomendacao.py` ("Ponto de extensão para v2:
trocar por scikit-learn NearestNeighbors comparando o vetor de lacunas do
aluno com o conteúdo disponível") — complementando, não substituindo, a
recomendação por ordem curricular: aquela decide "qual é o próximo passo
da trilha"; esta decide "que outro conteúdo ajuda a reforçar esse ponto
fraco", mesmo que esteja em outro tema.
"""

import numpy as np
from sklearn.neighbors import NearestNeighbors
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subtema import Subtema
from app.services.embeddings import gerar_embeddings

# Cache em memória de todos os subtemas + seus embeddings. Mesma ressalva
# de `classificacao_ia.py`: MVP simples, sem invalidação automática.
_cache_todos_subtemas: tuple[list[tuple[int, str]], np.ndarray] | None = None


async def _embeddings_todos_subtemas(db: AsyncSession):
    global _cache_todos_subtemas
    if _cache_todos_subtemas is not None:
        return _cache_todos_subtemas

    result = await db.execute(select(Subtema))
    subtemas = result.scalars().all()

    textos = [f"{s.nome}. {s.descricao_ia or ''}".strip() for s in subtemas]
    embeddings = gerar_embeddings(textos)
    ids_nomes = [(s.id, s.nome) for s in subtemas]

    _cache_todos_subtemas = (ids_nomes, embeddings)
    return _cache_todos_subtemas


def invalidar_cache_global() -> None:
    """Chamar após criar/editar qualquer subtema, para forçar recálculo."""
    global _cache_todos_subtemas
    _cache_todos_subtemas = None


async def subtemas_relacionados(
    db: AsyncSession, subtema_id: int, k: int = 3
) -> list[tuple[int, str, float]]:
    """
    Sugere até `k` subtemas conceitualmente relacionados a `subtema_id`,
    por similaridade de cosseno dos embeddings — mesmo que estejam em
    outro tema/matéria. Útil para reforço cruzado quando o aluno erra
    muito num assunto específico (ex: fraqueza em "Metabolismo
    Energético" pode se beneficiar de revisar "Organelas Citoplasmáticas",
    já que ambos compartilham conceitos de estrutura celular).

    Retorna lista de (subtema_id, nome, similaridade), ordenada da mais
    relacionada para a menos relacionada, excluindo o próprio subtema.
    """
    ids_nomes, embeddings = await _embeddings_todos_subtemas(db)
    if len(ids_nomes) < 2:
        return []

    indice_alvo = next((i for i, (sid, _) in enumerate(ids_nomes) if sid == subtema_id), None)
    if indice_alvo is None:
        return []

    # +1 vizinhos porque o próprio subtema sempre aparece como o vizinho
    # mais próximo de si mesmo (similaridade 1.0) e é descartado depois.
    k_efetivo = min(k + 1, len(ids_nomes))
    modelo = NearestNeighbors(n_neighbors=k_efetivo, metric="cosine")
    modelo.fit(embeddings)

    distancias, indices = modelo.kneighbors([embeddings[indice_alvo]])

    relacionados: list[tuple[int, str, float]] = []
    for dist, idx in zip(distancias[0], indices[0], strict=True):
        sid, nome = ids_nomes[idx]
        if sid == subtema_id:
            continue
        # NearestNeighbors com metric="cosine" retorna distância = 1 - similaridade.
        similaridade = round(1 - float(dist), 3)
        relacionados.append((sid, nome, similaridade))

    return relacionados[:k]
