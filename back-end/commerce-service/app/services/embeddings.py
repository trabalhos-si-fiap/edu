"""
Módulo de embeddings do Commerce Service — mesma técnica e biblioteca já
usadas no Learning Service (`sentence-transformers`), aplicada aqui para
sugerir produtos substitutos por similaridade semântica real, em vez de
só "mesma categoria" (ver `services/substituicao_ia.py`).

O modelo é carregado uma única vez por processo (singleton). Se o
download falhar (sem internet, huggingface.co indisponível), quem chama
`gerar_embeddings`/`gerar_embedding` recebe a exceção e deve degradar
graciosamente — nunca deixar isso derrubar o fluxo de reportar uma
ocorrência (ver nota em `substituicao_ia.py`, achado real testando o
mesmo padrão no Learning Service).
"""

import numpy as np
from sentence_transformers import SentenceTransformer

NOME_MODELO = "paraphrase-multilingual-MiniLM-L12-v2"

_modelo: SentenceTransformer | None = None


def _get_modelo() -> SentenceTransformer:
    global _modelo
    if _modelo is None:
        _modelo = SentenceTransformer(NOME_MODELO)
    return _modelo


def gerar_embedding(texto: str) -> np.ndarray:
    modelo = _get_modelo()
    return modelo.encode(texto, convert_to_numpy=True, normalize_embeddings=True)


def gerar_embeddings(textos: list[str]) -> np.ndarray:
    modelo = _get_modelo()
    if not textos:
        return np.array([])
    return modelo.encode(textos, convert_to_numpy=True, normalize_embeddings=True)


def similaridade_cosseno(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))
