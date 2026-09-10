import uuid
from decimal import Decimal

from edu_common.security import create_access_token, verify_password
from sqlalchemy import select

from app.config import settings
from app.models.carregamento import Carregamento
from app.models.pedido import Order
from app.models.transportadora import Carrier
from app.services.status_pedido import StatusPedido

ADMIN = "00000000-0000-0000-0000-0000000000a1"


def headers_for(role: str, sub: str = ADMIN) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(sub, role, settings.jwt_secret)}"}


async def _seed_transportadora(db_session) -> Carrier:
    carrier = Carrier(
        name="Expresso Cajamar",
        location="Cajamar, SP",
        email="operacao@expresso.example",
        average_delivery_days=2,
        rating=Decimal("4.5"),
        sla_percentage=Decimal("97.50"),
    )
    db_session.add(carrier)
    await db_session.commit()
    await db_session.refresh(carrier)
    return carrier


async def _seed_pedido(
    db_session,
    *,
    status: str = StatusPedido.AGUARDANDO_COLETA.value,
    origem: tuple[str | None, str | None, str | None] = (
        "Cajamar, SP",
        "-23.355800",
        "-46.876900",
    ),
) -> Order:
    rotulo, lat, lng = origem
    pedido = Order(
        user_id=uuid.uuid4(),
        status=status,
        total=Decimal("100.00"),
        origem_rotulo=rotulo,
        origem_lat=Decimal(lat) if lat is not None else None,
        origem_lng=Decimal(lng) if lng is not None else None,
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


async def test_creating_a_shipment_requires_admin(client, db_session):
    carrier = await _seed_transportadora(db_session)
    for papel in ("student", "separador", "entregador"):
        response = await client.post(
            "/shipments",
            headers=headers_for(papel),
            json={"transportadora_id": carrier.id},
        )
        assert response.status_code == 403


async def test_creating_a_shipment_returns_the_credential_once(client, db_session):
    carrier = await _seed_transportadora(db_session)

    response = await client.post(
        "/shipments", headers=headers_for("admin"), json={"transportadora_id": carrier.id}
    )

    assert response.status_code == 201
    corpo = response.json()
    assert len(corpo["codigo"]) == 8
    assert len(corpo["senha"]) == 12

    carregamento = (
        await db_session.execute(select(Carregamento).where(Carregamento.id == corpo["id"]))
    ).scalar_one()
    # A senha é guardada só como hash, e o hash confere com o que saiu na
    # resposta — regra 5 do CLAUDE.md.
    assert carregamento.senha_hash != corpo["senha"]
    assert verify_password(corpo["senha"], carregamento.senha_hash)


async def test_the_listing_never_carries_the_credential(client, db_session):
    carrier = await _seed_transportadora(db_session)
    await client.post(
        "/shipments", headers=headers_for("admin"), json={"transportadora_id": carrier.id}
    )

    listagem = await client.get("/shipments", headers=headers_for("admin"))

    assert listagem.status_code == 200
    item = listagem.json()["items"][0]
    assert "senha" not in item
    assert "senha_hash" not in item
    # O código não é segredo (ele identifica o lote); a senha é.
    assert len(item["codigo"]) == 8


async def test_assigning_an_order_freezes_the_shipment_origin(client, db_session):
    carrier = await _seed_transportadora(db_session)
    criado = (
        await client.post(
            "/shipments", headers=headers_for("admin"), json={"transportadora_id": carrier.id}
        )
    ).json()
    pedido = await _seed_pedido(db_session)

    response = await client.post(
        f"/shipments/{criado['id']}/orders",
        headers=headers_for("admin"),
        json={"pedido_id": str(pedido.id)},
    )

    assert response.status_code == 200
    await db_session.refresh(pedido)
    assert pedido.carregamento_id == criado["id"]
    # A transportadora do lote passa a ser a do pedido: o rastreio do aluno
    # mostra `orders.carrier_name` a partir da task 6 (D12).
    assert pedido.carrier_name == carrier.name

    carregamento = (
        await db_session.execute(select(Carregamento).where(Carregamento.id == criado["id"]))
    ).scalar_one()
    assert carregamento.origem_rotulo == "Cajamar, SP"
    assert carregamento.origem_lat == Decimal("-23.355800")


async def test_a_shipment_carries_one_origin_only(client, db_session):
    """Um carregamento é o lote que sai de UMA origem. Sem essa regra a
    interpolação da posição (task 6) não teria ponto de partida."""
    carrier = await _seed_transportadora(db_session)
    criado = (
        await client.post(
            "/shipments", headers=headers_for("admin"), json={"transportadora_id": carrier.id}
        )
    ).json()
    primeiro = await _seed_pedido(db_session)
    outro = await _seed_pedido(db_session, origem=("Osasco, SP", "-23.532700", "-46.792000"))

    await client.post(
        f"/shipments/{criado['id']}/orders",
        headers=headers_for("admin"),
        json={"pedido_id": str(primeiro.id)},
    )
    response = await client.post(
        f"/shipments/{criado['id']}/orders",
        headers=headers_for("admin"),
        json={"pedido_id": str(outro.id)},
    )

    assert response.status_code == 409
    await db_session.refresh(outro)
    assert outro.carregamento_id is None


async def test_a_null_origin_first_order_still_freezes_the_shipment_origin(client, db_session):
    """Fix round 1: a sentinela de congelamento é "o lote já tem pedido?",
    não "o rótulo está vazio?". Um primeiro pedido sem fornecedor resolvido
    (origem nula) tem que congelar o lote em "sem origem" — não deixar a
    porta aberta para um segundo pedido, de origem real, se misturar."""
    carrier = await _seed_transportadora(db_session)
    criado = (
        await client.post(
            "/shipments", headers=headers_for("admin"), json={"transportadora_id": carrier.id}
        )
    ).json()
    sem_origem = await _seed_pedido(db_session, origem=(None, None, None))
    com_origem = await _seed_pedido(db_session)

    primeira = await client.post(
        f"/shipments/{criado['id']}/orders",
        headers=headers_for("admin"),
        json={"pedido_id": str(sem_origem.id)},
    )
    segunda = await client.post(
        f"/shipments/{criado['id']}/orders",
        headers=headers_for("admin"),
        json={"pedido_id": str(com_origem.id)},
    )

    assert primeira.status_code == 200
    assert segunda.status_code == 409
    await db_session.refresh(com_origem)
    assert com_origem.carregamento_id is None


async def test_two_null_origin_orders_share_a_shipment(client, db_session):
    """Um lote de pedidos sem origem é um lote coerente (o simulador de
    posição degrada para posição nula) — a regra proíbe MISTURAR origens,
    não proíbe origem nula."""
    carrier = await _seed_transportadora(db_session)
    criado = (
        await client.post(
            "/shipments", headers=headers_for("admin"), json={"transportadora_id": carrier.id}
        )
    ).json()
    primeiro = await _seed_pedido(db_session, origem=(None, None, None))
    segundo = await _seed_pedido(db_session, origem=(None, None, None))

    primeira = await client.post(
        f"/shipments/{criado['id']}/orders",
        headers=headers_for("admin"),
        json={"pedido_id": str(primeiro.id)},
    )
    segunda = await client.post(
        f"/shipments/{criado['id']}/orders",
        headers=headers_for("admin"),
        json={"pedido_id": str(segundo.id)},
    )

    assert (primeira.status_code, segunda.status_code) == (200, 200)


async def test_an_order_belongs_to_one_shipment(client, db_session):
    carrier = await _seed_transportadora(db_session)
    um = (
        await client.post(
            "/shipments", headers=headers_for("admin"), json={"transportadora_id": carrier.id}
        )
    ).json()
    outro = (
        await client.post(
            "/shipments", headers=headers_for("admin"), json={"transportadora_id": carrier.id}
        )
    ).json()
    pedido = await _seed_pedido(db_session)

    await client.post(
        f"/shipments/{um['id']}/orders",
        headers=headers_for("admin"),
        json={"pedido_id": str(pedido.id)},
    )
    response = await client.post(
        f"/shipments/{outro['id']}/orders",
        headers=headers_for("admin"),
        json={"pedido_id": str(pedido.id)},
    )

    assert response.status_code == 409


async def test_reassigning_to_the_same_shipment_is_idempotent(client, db_session):
    carrier = await _seed_transportadora(db_session)
    criado = (
        await client.post(
            "/shipments", headers=headers_for("admin"), json={"transportadora_id": carrier.id}
        )
    ).json()
    pedido = await _seed_pedido(db_session)

    primeira = await client.post(
        f"/shipments/{criado['id']}/orders",
        headers=headers_for("admin"),
        json={"pedido_id": str(pedido.id)},
    )
    segunda = await client.post(
        f"/shipments/{criado['id']}/orders",
        headers=headers_for("admin"),
        json={"pedido_id": str(pedido.id)},
    )

    assert (primeira.status_code, segunda.status_code) == (200, 200)


async def test_creating_a_shipment_publishes_the_credential_for_the_carrier(
    client, db_session, _stub_publish_event
):
    """A task 9 transforma este evento em e-mail. A senha viaja em claro UMA
    vez, aqui — e não é gravada em notificação nenhuma nem logada."""
    carrier = await _seed_transportadora(db_session)

    criado = (
        await client.post(
            "/shipments", headers=headers_for("admin"), json={"transportadora_id": carrier.id}
        )
    ).json()

    eventos = [p for chave, p in _stub_publish_event if chave == "shipment.created"]
    assert len(eventos) == 1
    assert eventos[0]["codigo"] == criado["codigo"]
    assert eventos[0]["senha"] == criado["senha"]
    assert eventos[0]["transportadora_email"] == carrier.email


async def test_unknown_carrier_is_404(client):
    response = await client.post(
        "/shipments", headers=headers_for("admin"), json={"transportadora_id": 999999}
    )
    assert response.status_code == 404


async def test_the_order_listing_is_paginated(client, db_session):
    carrier = await _seed_transportadora(db_session)
    criado = (
        await client.post(
            "/shipments", headers=headers_for("admin"), json={"transportadora_id": carrier.id}
        )
    ).json()

    response = await client.get(
        f"/shipments/{criado['id']}/orders?limit=5000", headers=headers_for("admin")
    )

    assert response.status_code == 422
