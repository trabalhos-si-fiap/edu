"""Testes de caracterização de `decidir_acao_tema` (services/decisao.py).

O brief desta task supunha uma assinatura `decidir_acao(dominio,
tem_tema_anterior) -> str`. A função real é `decidir_acao_tema(dominio_tema,
existe_tema_anterior) -> AcaoTema` (um `StrEnum`), com limiares
`LIMIAR_RETROCEDER_TEMA = 0.3` e `LIMIAR_AVANCAR_TEMA = 0.7`. Confirmado
lendo `app/services/decisao.py` antes de escrever estes testes. O
comportamento descrito pelo brief (avancar >= 0.7, estudar entre os
limiares, retroceder < 0.3 só quando existe tema anterior) bateu com o
código real — só os nomes de função/parâmetro mudaram.
"""

from app.services.decisao import (
    LIMIAR_AVANCAR_TEMA,
    LIMIAR_RETROCEDER_TEMA,
    AcaoTema,
    decidir_acao_tema,
)


def test_high_mastery_advances():
    assert decidir_acao_tema(dominio_tema=0.85, existe_tema_anterior=True) == AcaoTema.AVANCAR


def test_mid_mastery_studies():
    assert decidir_acao_tema(dominio_tema=0.50, existe_tema_anterior=True) == AcaoTema.ESTUDAR


def test_low_mastery_goes_back_when_there_is_a_previous_topic():
    assert decidir_acao_tema(dominio_tema=0.20, existe_tema_anterior=True) == AcaoTema.RETROCEDER


def test_low_mastery_studies_when_there_is_no_previous_topic():
    assert decidir_acao_tema(dominio_tema=0.20, existe_tema_anterior=False) == AcaoTema.ESTUDAR


def test_boundary_at_seventy_percent_advances():
    assert (
        decidir_acao_tema(dominio_tema=LIMIAR_AVANCAR_TEMA, existe_tema_anterior=True)
        == AcaoTema.AVANCAR
    )


def test_boundary_at_thirty_percent_studies():
    # dominio < 0.3 é quem retrocede; em 0.3 exato não é "menor que", então
    # não retrocede — cai em "estudar" (não atinge o limiar de avançar).
    assert (
        decidir_acao_tema(dominio_tema=LIMIAR_RETROCEDER_TEMA, existe_tema_anterior=True)
        == AcaoTema.ESTUDAR
    )


def test_return_value_is_the_acao_tema_enum_not_a_bare_string():
    resultado = decidir_acao_tema(dominio_tema=0.85, existe_tema_anterior=True)
    assert isinstance(resultado, AcaoTema)
    assert resultado == "avancar"  # StrEnum: compara igual ao valor string
