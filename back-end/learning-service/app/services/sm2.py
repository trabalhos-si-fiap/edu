from datetime import UTC, datetime, timedelta


def atualizar_revisao(
    dominio: float, intervalo_atual_dias: float, streak: int
) -> tuple[float, int, datetime]:
    """
    Algoritmo de repetição espaçada (baseado no SM-2, usado no Anki).
    Retorna (novo_intervalo_dias, novo_streak, proxima_revisao_datetime).
    """
    if dominio < 0.4:
        novo_intervalo = 1.0
        novo_streak = 0
    elif dominio < 0.7:
        novo_intervalo = max(3.0, intervalo_atual_dias * 1.3)
        novo_streak = 0
    else:
        fator = 1.5 + (streak * 0.3)
        novo_intervalo = intervalo_atual_dias * fator
        novo_streak = streak + 1

    proxima_revisao = datetime.now(UTC) + timedelta(days=novo_intervalo)
    return novo_intervalo, novo_streak, proxima_revisao
