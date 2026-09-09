"""Trava a forma do schema que a spec B introduz.

Não roda alembic (a suíte monta o schema com `Base.metadata.create_all` —
ver `tests/conftest.py::test_engine`). O que este arquivo garante é que os
MODELS declaram o que as tasks 2..13 consomem, com os tamanhos medidos no
Java de origem. A prova de que a REVISION aplica está no passo 6 desta
task, feita à mão contra `commerce_test`, e registrada no relatório.
"""

import uuid
from decimal import Decimal

from app.models.estoque_ajuste import EstoqueAjuste
from app.models.ocorrencia import Ocorrencia
from app.models.pedido import Order
from app.models.produto import Estoque, Fornecedor, Product
from app.models.transportadora import Carrier, CarrierStatus


def test_fornecedor_carries_a_shipping_origin():
    cols = Fornecedor.__table__.columns
    assert cols["origem_rotulo"].type.length == 120
    assert cols["origem_rotulo"].nullable is False
    assert cols["origem_lat"].nullable is True
    assert cols["origem_lng"].nullable is True


def test_product_has_sku_and_active():
    cols = Product.__table__.columns
    assert cols["sku"].type.length == 60
    # Índice único PARCIAL em `__table_args__` (não `Column(unique=True)`):
    # `Column.unique` fica `None`, não `True`. Ver `uq_products_sku` abaixo.
    idx = {i.name: i for i in Product.__table__.indexes}["uq_products_sku"]
    assert idx.unique is True
    assert "sku <> ''" in str(idx.dialect_options["postgresql"]["where"])
    assert cols["active"].nullable is False


def test_estoque_has_a_minimum():
    assert Estoque.__table__.columns["estoque_minimo"].nullable is False


def test_estoque_ajuste_records_both_quantities_and_an_author():
    cols = EstoqueAjuste.__table__.columns
    assert set(cols.keys()) == {
        "id",
        "estoque_id",
        "quantidade_anterior",
        "quantidade_nova",
        "motivo",
        "autor_id",
        "criado_em",
    }
    assert cols["motivo"].type.length == 300
    assert cols["autor_id"].nullable is False


def test_carrier_matches_the_java_field_widths():
    cols = Carrier.__table__.columns
    assert cols["name"].type.length == 150
    assert cols["location"].type.length == 150
    assert cols["email"].type.length == 254
    assert (cols["rating"].type.precision, cols["rating"].type.scale) == (2, 1)
    assert (cols["sla_percentage"].type.precision, cols["sla_percentage"].type.scale) == (5, 2)


def test_carrier_status_is_an_enum_of_two_values():
    assert [s.value for s in CarrierStatus] == ["ACTIVE", "INACTIVE"]


def test_ocorrencia_points_at_a_carrier_optionally():
    col = Ocorrencia.__table__.columns["transportadora_id"]
    assert col.nullable is True
    assert {fk.target_fullname for fk in col.foreign_keys} == {"carriers.id"}


def test_order_snapshots_the_shipping_origin():
    cols = Order.__table__.columns
    assert cols["origem_rotulo"].type.length == 120
    for name in ("origem_rotulo", "origem_lat", "origem_lng"):
        assert cols[name].nullable is True


async def test_the_new_tables_are_created_by_the_suite_schema(db_session):
    """Se um model novo não for importado por `conftest.py::test_engine`,
    `create_all` não o cria e todo teste das tasks 2..13 morre com
    `UndefinedTableError` — um sintoma que não aponta para a causa."""
    fornecedor = Fornecedor(nome="Edu", origem_rotulo="Aclimação, SP")
    db_session.add(fornecedor)
    await db_session.commit()

    produto = Product(name="P", type="apostila", price=Decimal("1.00"), sku="SKU-1")
    db_session.add(produto)
    await db_session.commit()

    estoque = Estoque(produto_id=produto.id, fornecedor_id=fornecedor.id, quantidade=5)
    db_session.add(estoque)
    await db_session.commit()

    db_session.add(
        EstoqueAjuste(
            estoque_id=estoque.id,
            quantidade_anterior=5,
            quantidade_nova=7,
            motivo="Recebimento de lote",
            autor_id=uuid.UUID(int=1),
        )
    )
    db_session.add(
        Carrier(
            name="Transportadora X",
            location="São Paulo, SP",
            email="x@example.com",
            average_delivery_days=3,
            rating=Decimal("4.5"),
            sla_percentage=Decimal("98.50"),
            status=CarrierStatus.ACTIVE.value,
        )
    )
    await db_session.commit()
