from enum import StrEnum


class AcaoTema(StrEnum):
    """As 3 saídas possíveis de um diagnóstico, no nível do Tema (ex: Citologia)."""

    ESTUDAR = "estudar"  # recomienda estudo nos subtemas fracos do tema atual
    AVANCAR = "avancar"  # bom domínio geral, sugere o próximo tema da trilha
    RETROCEDER = "retroceder"  # desempenho muito baixo, sugere voltar ao tema pré-requisito


class ClassificacaoSubtema(StrEnum):
    """Classificação individual de cada subtema dentro do tema avaliado."""

    ESTUDAR_DO_ZERO = "estudar_do_zero"  # dominio < LIMIAR_CRITICO_SUBTEMA
    REVISAR = "revisar"  # entre os dois limiares
    DOMINADO = "dominado"  # dominio >= LIMIAR_DOMINIO_SUBTEMA


# Limiares por subtema (granularidade fina, dentro do tema avaliado).
LIMIAR_CRITICO_SUBTEMA = 0.4
LIMIAR_DOMINIO_SUBTEMA = 0.7

# Limiares no nível do tema (decisão de avançar/retroceder/estudar).
# Propositalmente mais permissivos que os de subtema: um aluno pode ir mal
# em UM subtema específico sem que isso signifique que precisa retroceder
# no tema inteiro — só recomendamos retroceder se o desempenho geral foi
# realmente ruim.
LIMIAR_RETROCEDER_TEMA = 0.3
LIMIAR_AVANCAR_TEMA = 0.7


def classificar_subtema(dominio: float) -> ClassificacaoSubtema:
    if dominio < LIMIAR_CRITICO_SUBTEMA:
        return ClassificacaoSubtema.ESTUDAR_DO_ZERO
    if dominio < LIMIAR_DOMINIO_SUBTEMA:
        return ClassificacaoSubtema.REVISAR
    return ClassificacaoSubtema.DOMINADO


def decidir_acao_tema(dominio_tema: float, existe_tema_anterior: bool) -> AcaoTema:
    """
    Decide a ação no nível do tema inteiro (as 3 saídas do fluxo).

    Se o desempenho foi muito ruim mas não existe tema pré-requisito
    (ex: já é o primeiro tema da matéria), não há para onde retroceder —
    a ação cai para ESTUDAR, recomendando reforço nos subtemas fracos do
    próprio tema atual em vez de mandar o aluno para lugar nenhum.
    """
    if dominio_tema < LIMIAR_RETROCEDER_TEMA and existe_tema_anterior:
        return AcaoTema.RETROCEDER
    if dominio_tema >= LIMIAR_AVANCAR_TEMA:
        return AcaoTema.AVANCAR
    return AcaoTema.ESTUDAR
