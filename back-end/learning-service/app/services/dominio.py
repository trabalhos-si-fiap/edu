def calcular_dominio(respostas: list[tuple[bool, int]]) -> float:
    """
    respostas: lista de (acertou, peso_dificuldade)
    Retorna um valor entre 0.0 e 1.0, ponderado pela dificuldade de cada questão
    (acertar uma questão difícil vale mais que acertar uma fácil).
    """
    if not respostas:
        return 0.0

    pontos_possiveis = sum(peso for _, peso in respostas)
    pontos_obtidos = sum(peso for acertou, peso in respostas if acertou)

    if pontos_possiveis == 0:
        return 0.0

    return round(pontos_obtidos / pontos_possiveis, 3)


def calcular_dominio_tema(dominios_por_subtema: dict[int, tuple[float, int]]) -> float:
    """
    Agrega o domínio de vários subtemas em um único domínio do tema, para
    decidir se o aluno deve avançar/estudar/retroceder no tema como um todo.

    dominios_por_subtema: {subtema_id: (dominio_do_subtema, qtd_questoes_respondidas)}
    A média é ponderada pela quantidade de questões de cada subtema, para
    que um subtema pouco testado (ex: 1 questão) não pese tanto quanto um
    subtema bem coberto (ex: 6 questões) na decisão final.
    """
    total_questoes = sum(qtd for _, qtd in dominios_por_subtema.values())
    if total_questoes == 0:
        return 0.0

    soma_ponderada = sum(dominio * qtd for dominio, qtd in dominios_por_subtema.values())
    return round(soma_ponderada / total_questoes, 3)
