"""Posição do carregamento: a porta de escrita, a leitura, e o simulador.

`registrar_posicao` é a ÚNICA função que escreve em `posicao_entrega` — o
teste `test_registrar_posicao_is_the_write_door_and_needs_no_simulator` a
chama direto, sem passar pelo simulador, porque é isso que prova que a
interface serve a um GPS de verdade e não só à simulação desta spec.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.models.carregamento import PosicaoEntrega
from app.services.posicao import registrar_posicao, ultima_posicao
from app.services.simulador_posicao import (
    avancar_carregamentos,
    fracao_percorrida,
    interpolar,
)
from app.services.status_pedido import StatusPedido

ORIGEM = (Decimal("-23.355800"), Decimal("-46.876900"))
DESTINO = (Decimal("-23.561414"), Decimal("-46.655881"))


def test_the_fraction_is_zero_at_the_start_and_one_at_the_end():
    inicio = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)
    duracao = timedelta(minutes=10)
    assert fracao_percorrida(inicio, inicio, duracao) == 0.0
    assert fracao_percorrida(inicio, inicio + duracao, duracao) == 1.0


def test_the_fraction_never_passes_the_destination():
    """Depois do prazo o entregador chegou; ele não continua andando para
    além do endereço."""
    inicio = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)
    assert fracao_percorrida(inicio, inicio + timedelta(hours=5), timedelta(minutes=10)) == 1.0


def test_the_interpolation_is_monotonic_between_origin_and_destination():
    anterior = ORIGEM
    for passo in range(1, 11):
        atual = interpolar(ORIGEM, DESTINO, passo / 10)
        # O destino está a sudeste da origem: latitude cai, longitude sobe.
        assert atual[0] < anterior[0]
        assert atual[1] > anterior[1]
        anterior = atual
    assert interpolar(ORIGEM, DESTINO, 1.0) == DESTINO


async def test_registrar_posicao_is_the_write_door_and_needs_no_simulator(
    db_session, seed_carregamento
):
    """Chamada DIRETO, sem passar pelo simulador — é isso que prova que a
    interface serve a um GPS de verdade. Trocar de fonte é acrescentar um
    chamador, não reescrever leitura, model ou tela."""
    carregamento = await seed_carregamento()

    await registrar_posicao(
        db_session, carregamento.id, Decimal("-23.400000"), Decimal("-46.800000")
    )

    gravadas = (
        (
            await db_session.execute(
                select(PosicaoEntrega).where(PosicaoEntrega.carregamento_id == carregamento.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(gravadas) == 1
    assert gravadas[0].lat == Decimal("-23.400000")


async def test_the_write_door_quantizes_the_coordinates_it_is_given(
    db_session, seed_carregamento, monkeypatch
):
    """A quantização é garantia da PORTA, não de quem chama.

    O simulador já quantizava por conta própria — mas o propósito declarado
    de `registrar_posicao` é que um chamador futuro (um aparelho com GPS,
    mandando as sete ou oito casas que o hardware produz) herde as garantias
    sem repeti-las.

    A asserção é sobre o objeto no momento do `db.add`, e NÃO sobre o valor
    lido de volta, de propósito: o Postgres arredonda sozinho ao gravar numa
    coluna `Numeric(9, 6)`, então o ida-e-volta esconde exatamente a
    diferença que este teste existe para pegar. O que se quer travar é que a
    função entrega um valor já na precisão da coluna — e não que o banco
    conserte depois.
    """
    carregamento = await seed_carregamento()
    adicionados = []
    add_original = db_session.add

    def _espiar(obj):
        adicionados.append((obj.lat, obj.lng))
        add_original(obj)

    monkeypatch.setattr(db_session, "add", _espiar)

    await registrar_posicao(
        db_session, carregamento.id, Decimal("-23.4000004999"), Decimal("-46.8000001")
    )

    assert adicionados == [(Decimal("-23.400000"), Decimal("-46.800000"))]


async def test_positions_accumulate_as_a_path(db_session, seed_carregamento):
    """Série temporal, não campo único: o mapa desenha o caminho."""
    carregamento = await seed_carregamento()

    for lat in ("-23.40", "-23.45", "-23.50"):
        await registrar_posicao(db_session, carregamento.id, Decimal(lat), Decimal("-46.80"))

    todas = (
        (
            await db_session.execute(
                select(PosicaoEntrega).where(PosicaoEntrega.carregamento_id == carregamento.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(todas) == 3
    ultima = await ultima_posicao(db_session, carregamento.id)
    assert ultima.lat == Decimal("-23.500000")


async def test_the_simulator_only_moves_shipments_in_transit(
    db_session, seed_carregamento_com_pedido
):
    parado, _ = await seed_carregamento_com_pedido(status=StatusPedido.AGUARDANDO_COLETA.value)
    andando, _ = await seed_carregamento_com_pedido(status=StatusPedido.EM_TRANSITO.value)

    avancados = await avancar_carregamentos(db_session, datetime.now(UTC))

    assert avancados == 1
    assert await ultima_posicao(db_session, parado.id) is None
    assert await ultima_posicao(db_session, andando.id) is not None


async def test_the_simulator_skips_an_order_without_a_frozen_destination(
    db_session, seed_carregamento_com_pedido
):
    """Sem coordenada de destino não há segmento para interpolar. O pedido é
    ignorado e o rastreio devolve posição nula — o caminho de degradação que
    a spec prevê, não uma exceção."""
    carregamento, _ = await seed_carregamento_com_pedido(
        status=StatusPedido.EM_TRANSITO.value, destino=None
    )

    avancados = await avancar_carregamentos(db_session, datetime.now(UTC))

    assert avancados == 0
    assert await ultima_posicao(db_session, carregamento.id) is None
