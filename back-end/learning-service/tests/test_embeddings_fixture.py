"""Prova de que a fixture `fake_encoder` (tests/conftest.py) realmente
intercepta o carregamento do modelo de embeddings, em vez de só coincidir
com testes que nunca tocam esse caminho de código.

Sem a fixture (ou com o alvo de monkeypatch errado), qualquer uma destas
chamadas dispararia `SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")`
de verdade — um download de centenas de MB na primeira execução.
"""

import numpy as np

from app.services.embeddings import gerar_embedding, gerar_embeddings, similaridade_cosseno


def test_gerar_embedding_de_um_texto_devolve_vetor_1d_determinístico():
    vetor = gerar_embedding("Membrana Plasmática")
    assert isinstance(vetor, np.ndarray)
    assert vetor.ndim == 1
    # Mesma entrada -> mesmo vetor (determinístico, sem chamada de rede).
    assert np.array_equal(vetor, gerar_embedding("Membrana Plasmática"))


def test_gerar_embeddings_de_lista_devolve_matriz_2d():
    textos = ["Membrana Plasmática", "Organelas Citoplasmáticas", "Núcleo"]
    matriz = gerar_embeddings(textos)
    assert isinstance(matriz, np.ndarray)
    assert matriz.shape == (3, 3)


def test_similaridade_cosseno_texto_consigo_mesmo_e_maxima():
    vetor = gerar_embedding("Metabolismo Energético")
    # similaridade_cosseno espera vetores normalizados; o fake não normaliza,
    # mas o produto de um vetor por ele mesmo ainda é o maior possível —
    # suficiente para provar que o caminho de código roda de ponta a ponta.
    assert similaridade_cosseno(vetor, vetor) >= similaridade_cosseno(
        vetor, gerar_embedding("Um texto completamente diferente e mais longo")
    )


def test_gerar_embeddings_de_lista_vazia_nao_chama_o_encoder(monkeypatch):
    chamado = False

    class EncoderQueNuncaDeveriaSerChamado:
        def encode(self, *args, **kwargs):
            nonlocal chamado
            chamado = True
            raise AssertionError("encode() não deveria ser chamado para lista vazia")

    monkeypatch.setattr(
        "app.services.embeddings._get_modelo", lambda: EncoderQueNuncaDeveriaSerChamado()
    )
    resultado = gerar_embeddings([])
    assert resultado.size == 0
    assert chamado is False
