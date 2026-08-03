"""
Módulo central de embeddings do Learning Service. Usa sentence-transformers
(a mesma biblioteca já empregada no Chatbot Service para o RAG) para gerar
representações vetoriais de texto em português, usadas para:

  1. Classificar automaticamente questões importadas do ENEM no subtema
     correto (ver `classificacao_ia.py`), sem mapeamento manual.
  2. Recomendar subtemas conceitualmente relacionados via similaridade
     semântica (ver `recomendacao_semantica.py`).

O modelo é carregado uma única vez por processo (singleton) e mantido em
memória — o primeiro request após subir o container é mais lento (baixa e
carrega o modelo, ~470MB); requests seguintes reaproveitam a instância.
"""

import numpy as np
from sentence_transformers import SentenceTransformer

# Modelo multilíngue leve, com bom desempenho em português — diferente do
# `all-MiniLM-L6-v2` usado no Chatbot Service (focado em inglês), porque
# aqui o texto de entrada é sempre português (enunciados de questões,
# nomes de subtemas).
NOME_MODELO = "paraphrase-multilingual-MiniLM-L12-v2"

_modelo: SentenceTransformer | None = None


def _get_modelo() -> SentenceTransformer:
    global _modelo
    if _modelo is None:
        _modelo = SentenceTransformer(NOME_MODELO)
    return _modelo


def gerar_embedding(texto: str) -> np.ndarray:
    """Embedding normalizado (norma 1) de um único texto."""
    modelo = _get_modelo()
    return modelo.encode(texto, convert_to_numpy=True, normalize_embeddings=True)


def gerar_embeddings(textos: list[str]) -> np.ndarray:
    """Embeddings normalizados de uma lista de textos, em lote (mais rápido
    que chamar `gerar_embedding` em loop)."""
    modelo = _get_modelo()
    if not textos:
        return np.array([])
    return modelo.encode(textos, convert_to_numpy=True, normalize_embeddings=True)


def similaridade_cosseno(a: np.ndarray, b: np.ndarray) -> float:
    """
    Similaridade de cosseno entre dois embeddings. Como ambos já vêm
    normalizados (norma 1) de `gerar_embedding`/`gerar_embeddings`, o
    produto escalar já É a similaridade de cosseno — não precisa dividir
    pelas normas novamente.
    """
    return float(np.dot(a, b))
