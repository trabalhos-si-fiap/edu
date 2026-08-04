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


def test_gerar_embedding_devolve_float32_como_o_encoder_real():
    # fix round 1: a versão anterior do fake devolvia float64 (default do
    # numpy); sentence-transformers devolve float32.
    assert gerar_embedding("Membrana Plasmática").dtype == np.float32


def test_similaridade_cosseno_texto_consigo_mesmo_e_exatamente_um():
    """fix round 1: a versão anterior deste teste enfraquecia a asserção
    para `>=` porque o fake ignorava `normalize_embeddings=True` — o mesmo
    texto contra si mesmo dava 86.0, não 1.0. `similaridade_cosseno` só É a
    similaridade de cosseno se os vetores tiverem norma 1 (ver seu
    docstring); a fixture agora normaliza quando o kwarg é passado, exatamente
    como todo call site real (`embeddings.py:38,52`) passa.
    """
    vetor = gerar_embedding("Metabolismo Energético")
    assert similaridade_cosseno(vetor, vetor) == pytest.approx(1.0)


def test_similaridade_cosseno_texto_vazio_nao_produz_nan():
    """fix round 1, guarda de norma zero: um texto vazio gera o vetor
    [0, 0, 0] antes de normalizar; dividir por norma zero sem guarda
    produziria NaN, que se propagaria sem erro por
    `NearestNeighbors(metric="cosine")` (usado em
    `recomendacao_semantica.py`) e seria engolido pelo `except Exception`
    largo em `diagnostico.py`.
    """
    vazio = gerar_embedding("")
    outro = gerar_embedding("qualquer coisa")
    assert not np.isnan(similaridade_cosseno(vazio, outro))
    assert not np.isnan(similaridade_cosseno(vazio, vazio))


def test_gerar_embeddings_de_lista_vazia_nao_chama_o_carregador(monkeypatch):
    """fix round 1: o teste anterior só provava que `.encode()` não era
    chamado — mas `gerar_embeddings` chamava `_get_modelo()` (que carrega o
    modelo de ~470MB) ANTES do guard de lista vazia, então em produção o
    carregamento acontecia de qualquer forma. Corrigido em `embeddings.py`
    (guard movido para antes de `_get_modelo()`); este teste agora prova
    isso remendando o PRÓPRIO carregador, não o encoder que ele devolveria.
    """
    chamadas: list[None] = []

    def _carregador_que_nunca_deveria_ser_chamado():
        chamadas.append(None)
        raise AssertionError("_get_modelo() não deveria ser chamado para lista vazia")

    monkeypatch.setattr(
        "app.services.embeddings._get_modelo", _carregador_que_nunca_deveria_ser_chamado
    )
    resultado = gerar_embeddings([])
    assert resultado.size == 0
    assert chamadas == []


@pytest.mark.slow
def test_marca_slow_faz_a_fixture_nao_remendar_nada():
    """Trava o mecanismo de opt-out em vez de só presumir que ele funciona
    (fix round 1, Important 2): sem isso, a marca `slow` era só decorativa
    — `fake_encoder` era `autouse=True` sem olhar para `request`, então
    remendava TODO teste, marcado `slow` ou não.

    Não chama `_get_modelo()` de verdade (isso baixaria o modelo real) — só
    confirma, por identidade de objeto, que a fixture devolveu cedo e
    deixou `_get_modelo` como a função original capturada no import deste
    módulo, antes de qualquer monkeypatch.
    """
    assert embeddings_module._get_modelo is _GET_MODELO_ORIGINAL
