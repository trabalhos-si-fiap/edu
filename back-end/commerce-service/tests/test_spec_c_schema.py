"""Trava a forma do schema que a spec C introduz.

Não roda alembic (a suíte monta o schema com `Base.metadata.create_all` — ver
`tests/conftest.py::test_engine`). O que este arquivo garante é que os MODELS
declaram o que as tasks 2..14 consomem. A prova de que a REVISION aplica está
no passo 6, feita à mão contra `commerce_test`, e registrada no relatório.
"""

from app.models.carregamento import Carregamento, PosicaoEntrega
from app.models.pedido import Order


def test_carregamento_carries_a_carrier_an_origin_and_a_credential():
    cols = Carregamento.__table__.columns
    assert cols["transportadora_id"].nullable is False
    assert cols["origem_rotulo"].type.length == 120
    assert cols["origem_rotulo"].nullable is False
    assert (cols["origem_lat"].type.precision, cols["origem_lat"].type.scale) == (9, 6)
    assert cols["codigo"].type.length == 12
    assert cols["codigo"].unique is True
    assert cols["senha_hash"].nullable is False


def test_carregamento_records_who_took_the_load_and_when():
    """Nome e contato do entregador são gravados no PRIMEIRO acesso (task 5),
    então nascem nulos — é isso que distingue um lote ainda não retirado."""
    cols = Carregamento.__table__.columns
    assert cols["entregador_nome"].nullable is True
    assert cols["entregador_nome"].type.length == 120
    assert cols["entregador_contato"].nullable is True
    assert cols["aberto_em"].nullable is True
    assert cols["criado_por"].nullable is False


def test_posicao_entrega_is_a_time_series_not_a_single_field():
    """Série temporal: `carregamento_id` NÃO é único. Um campo único não
    guarda caminho percorrido, e o mapa desenha o caminho."""
    cols = PosicaoEntrega.__table__.columns
    assert cols["carregamento_id"].nullable is False
    assert cols["carregamento_id"].unique is not True
    assert cols["lat"].nullable is False
    assert cols["lng"].nullable is False
    assert cols["registrado_em"].nullable is False


def test_order_points_at_a_shipment_and_freezes_the_destination():
    cols = Order.__table__.columns
    assert cols["carregamento_id"].nullable is True
    assert (cols["destino_lat"].type.precision, cols["destino_lat"].type.scale) == (9, 6)
    assert cols["destino_lng"].nullable is True
