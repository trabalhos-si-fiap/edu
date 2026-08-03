"""Testes de caracterização de `detectar_anomalias` — congelam o
comportamento ATUAL do serviço, não o que ele deveria fazer.

A assinatura real, confirmada lendo `app/services/deteccao_anomalia.py`
antes de escrever este arquivo, diverge da assumida no brief da task 14
(uma função pura `detectar_anomalias(contagens_por_dia, contagem_hoje)`):
a implementação real é `async def detectar_anomalias(db: AsyncSession,
dias_historico: int = 30) -> list[dict]` — ela mesma consulta o banco via
`_contagem_diaria_por_tipo`, agrupando por `func.date(EventLog.criado_em)`,
e só avalia os quatro tipos fixos em `TIPOS_MONITORADOS`. Os testes abaixo
foram reescritos para essa assinatura: em vez de montar dicts em memória,
inserem `EventLog` no banco de teste com `criado_em` explícito por dia.

Limiares (5 dias mínimos, z-score >= 2.0) entram como LITERAIS nos testes,
nunca como `MINIMO_DIAS_HISTORICO`/`LIMIAR_Z_SCORE` importados da própria
implementação — importar a constante manteria o teste verde mesmo que
alguém mudasse o limiar embaixo dele.
"""

from datetime import UTC, datetime, timedelta

from app.models.event_log import EventLog
from app.services.deteccao_anomalia import MINIMO_DIAS_HISTORICO, detectar_anomalias


def _timestamp_dias_atras(dias_atras: int) -> datetime:
    # Fixa o horário ao meio-dia UTC para que o agrupamento por
    # `func.date()` nunca dependa de em que hora do dia a suíte roda.
    agora = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)
    return agora - timedelta(days=dias_atras)


async def _registrar(db_session, tipo: str, dias_atras: int, quantidade: int) -> None:
    momento = _timestamp_dias_atras(dias_atras)
    for _ in range(quantidade):
        db_session.add(EventLog(tipo=tipo, payload={}, criado_em=momento))
    await db_session.commit()


def test_threshold_is_at_least_five_days():
    assert MINIMO_DIAS_HISTORICO >= 5


async def test_short_history_produces_no_result(db_session):
    # 3 dias de histórico — literal, não `MINIMO_DIAS_HISTORICO - 1`.
    for dia in range(1, 4):
        await _registrar(db_session, "order.created", dia, 10)
    await _registrar(db_session, "order.created", 0, 900)

    resultado = await detectar_anomalias(db_session, dias_historico=10)

    assert all(r["tipo_evento"] != "order.created" for r in resultado)


async def test_count_near_the_average_is_not_an_anomaly(db_session):
    historico = [10, 11, 9, 10, 12, 10, 11]
    for dia, quantidade in enumerate(historico, start=1):
        await _registrar(db_session, "order.created", dia, quantidade)
    await _registrar(db_session, "order.created", 0, 10)

    resultado = await detectar_anomalias(db_session, dias_historico=10)

    entrada = next(r for r in resultado if r["tipo_evento"] == "order.created")
    assert entrada["anomalia"] is False


async def test_count_far_above_the_average_is_an_anomaly(db_session):
    historico = [10, 11, 9, 10, 12, 10, 11]
    for dia, quantidade in enumerate(historico, start=1):
        await _registrar(db_session, "order.created", dia, quantidade)
    await _registrar(db_session, "order.created", 0, 500)

    resultado = await detectar_anomalias(db_session, dias_historico=10)

    entrada = next(r for r in resultado if r["tipo_evento"] == "order.created")
    assert entrada["anomalia"] is True
    assert entrada["contagem_hoje"] == 500


async def test_count_far_below_the_average_is_an_anomaly(db_session):
    historico = [100, 110, 90, 105, 95, 100, 108]
    for dia, quantidade in enumerate(historico, start=1):
        await _registrar(db_session, "order.created", dia, quantidade)
    # Nenhum evento hoje => contagem_hoje = 0, bem abaixo da média histórica.

    resultado = await detectar_anomalias(db_session, dias_historico=10)

    entrada = next(r for r in resultado if r["tipo_evento"] == "order.created")
    assert entrada["anomalia"] is True
    assert entrada["contagem_hoje"] == 0


async def test_only_monitored_event_types_are_evaluated(db_session):
    """`student.created` não está em `TIPOS_MONITORADOS` — mesmo com um pico
    idêntico ao de `order.created` (que está), ele nunca deve aparecer no
    resultado. Testar os dois tipos lado a lado prova que o filtro é real:
    se alguém removesse `order.created` da whitelist, ou adicionasse
    `student.created` a ela, este teste (e só ele) pegaria a mudança."""
    for dia in range(1, 8):
        await _registrar(db_session, "order.created", dia, 10)
        await _registrar(db_session, "student.created", dia, 10)
    await _registrar(db_session, "order.created", 0, 500)
    await _registrar(db_session, "student.created", 0, 500)

    resultado = await detectar_anomalias(db_session, dias_historico=10)

    tipos_no_resultado = {r["tipo_evento"] for r in resultado}
    assert "order.created" in tipos_no_resultado
    assert "student.created" not in tipos_no_resultado


async def test_zero_variance_history_does_not_divide_by_zero(db_session):
    """Histórico perfeitamente estável (desvio padrão zero). Se o serviço
    dividisse por `desvio_historico` sem essa guarda, isso levantaria
    `ZeroDivisionError` — comportamento errado, não uma característica a
    congelar (ver `deteccao_anomalia.py`: desvio zero => sem anomalia,
    nunca uma divisão)."""
    for dia in range(1, 8):
        await _registrar(db_session, "order.created", dia, 10)
    await _registrar(db_session, "order.created", 0, 10)

    resultado = await detectar_anomalias(db_session, dias_historico=10)

    entrada = next(r for r in resultado if r["tipo_evento"] == "order.created")
    assert entrada["anomalia"] is False
    assert entrada["z_score"] is None
