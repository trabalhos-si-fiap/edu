"""Prova de que a fixture `fake_encoder` (tests/conftest.py) realmente
intercepta o carregamento do modelo de embeddings, em vez de só coincidir
com testes que nunca tocam esse caminho de código.

Sem a fixture (ou com o alvo de monkeypatch errado), qualquer uma destas
chamadas dispararia `SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")`
de verdade — um download de centenas de MB na primeira execução.
"""

import numpy as np
import pytest

import app.services.embeddings as embeddings_module
from app.services.embeddings import gerar_embedding, gerar_embeddings, similaridade_cosseno

# Capturado no import deste módulo de teste, ANTES de qualquer fixture rodar
# — nesse momento `_get_modelo` é garantidamente a função real definida em
# `embeddings.py`, nunca uma versão já remendada por um teste anterior. Usado
# pelo teste `slow` abaixo para provar que a fixture realmente deixou o
# carregador intocado, em vez de assumir isso.
_GET_MODELO_ORIGINAL = embeddings_module._get_modelo


def test_gerar_embedding_de_um_texto_devolve_vetor_1d_deterministico():
    vetor = gerar_embedding("Caderno Universitário")
    assert isinstance(vetor, np.ndarray)
    assert vetor.ndim == 1
    # Mesma entrada -> mesmo vetor (determinístico, sem chamada de rede).
    assert np.array_equal(vetor, gerar_embedding("Caderno Universitário"))


def test_gerar_embeddings_de_lista_devolve_matriz_2d():
    textos = ["Caderno Universitário", "Caderno Colegial", "Lápis HB"]
    matriz = gerar_embeddings(textos)
    assert isinstance(matriz, np.ndarray)
    assert matriz.shape == (3, 3)


def test_gerar_embedding_devolve_float32_como_o_encoder_real():
    # sentence-transformers devolve float32; um fake que devolvesse o
    # float64 padrão do numpy divergiria silenciosamente desse contrato.
    assert gerar_embedding("Caderno Universitário").dtype == np.float32


def test_similaridade_cosseno_texto_consigo_mesmo_e_exatamente_um():
    """`similaridade_cosseno` só É a similaridade de cosseno se os vetores
    tiverem norma 1 (ver seu docstring em embeddings.py). Todo call site
    real passa `normalize_embeddings=True` (embeddings.py:32,39) — a
    fixture precisa honrar esse kwarg, senão o mesmo texto contra si mesmo
    devolveria o produto escalar bruto (>1.0), não 1.0, e o
    `LIMIAR_SIMILARIDADE` de `substituicao_ia.py` (0.35) ficaria calibrado
    contra uma escala que a fixture não reproduz.
    """
    vetor = gerar_embedding("Mochila Escolar")
    assert similaridade_cosseno(vetor, vetor) == pytest.approx(1.0)


def test_similaridade_cosseno_texto_vazio_nao_produz_nan():
    """Um texto vazio gera o vetor [0, 0, 0] antes de normalizar; dividir
    por norma zero sem guarda produziria NaN, que se propagaria sem erro
    até o `except Exception` largo de `sugerir_substitutos`
    (substituicao_ia.py), mascarando o problema como uma simples ausência
    de substitutos em vez de um bug de cálculo.
    """
    vazio = gerar_embedding("")
    outro = gerar_embedding("qualquer coisa")
    assert not np.isnan(similaridade_cosseno(vazio, outro))
    assert not np.isnan(similaridade_cosseno(vazio, vazio))


@pytest.mark.slow
def test_marca_slow_faz_a_fixture_nao_remendar_nada():
    """Trava o mecanismo de opt-out em vez de só presumir que ele funciona:
    sem checar `request.node.get_closest_marker("slow")`, `fake_encoder`
    (autouse=True) remendaria TODO teste, marcado `slow` ou não.

    Não chama `_get_modelo()` de verdade (isso baixaria o modelo real) — só
    confirma, por identidade de objeto, que a fixture devolveu cedo e
    deixou `_get_modelo` como a função original capturada no import deste
    módulo, antes de qualquer monkeypatch.
    """
    assert embeddings_module._get_modelo is _GET_MODELO_ORIGINAL
