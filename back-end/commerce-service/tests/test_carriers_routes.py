"""Cobertura de `/carriers` — porte do `CarrierController` do Java.

Rotas espelhadas de
`mobile_hybrid_app/api/src/main/java/com/edu/api/carrier/controller/
CarrierController.java`: listagem com `search`/`status`, detalhe, POST, PUT e
`PATCH /{id}/status`. O que NÃO é espelhado é o envelope de página do Spring
(`{content, totalElements, ...}`) — a frota inteira usa
`{items, total, limit, offset}` e o painel Angular é reescrito para ele
(decisão D9 do plano da spec B).
"""

from edu_common.security import create_access_token

from app.config import settings
from app.models.transportadora import Carrier


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(sub, role, settings.jwt_secret)}"}


_PAYLOAD = {
    "name": "Rápido Cajamar",
    "location": "Cajamar, SP",
    "email": "ops@rapidocajamar.com.br",
    "average_delivery_days": 3,
    "rating": "4.5",
    "sla_percentage": "98.50",
    "status": "ACTIVE",
}


async def _seed(db_session, *, name: str, status: str = "ACTIVE") -> Carrier:
    carrier = Carrier(
        name=name,
        location="São Paulo, SP",
        email="ops@example.com",
        average_delivery_days=2,
        rating=4,
        sla_percentage=95,
        status=status,
    )
    db_session.add(carrier)
    await db_session.commit()
    await db_session.refresh(carrier)
    return carrier


async def test_every_carrier_route_is_admin_only(client, db_session):
    carrier = await _seed(db_session, name="X")
    chamadas = [
        ("get", "/carriers", None),
        ("get", f"/carriers/{carrier.id}", None),
        ("post", "/carriers", _PAYLOAD),
        ("put", f"/carriers/{carrier.id}", _PAYLOAD),
        ("patch", f"/carriers/{carrier.id}/status", {"status": "INACTIVE"}),
    ]
    for metodo, url, corpo in chamadas:
        for papel in ("student", "separador", "entregador"):
            kwargs = {"headers": headers_for(papel)}
            if corpo is not None:
                kwargs["json"] = corpo
            response = await getattr(client, metodo)(url, **kwargs)
            assert response.status_code == 403, f"{metodo} {url} {papel}"


async def test_every_carrier_route_requires_a_credential(client, db_session):
    """Ruling 3: uma negativa por rota, não uma por grupo. Sem
    `Authorization`, o contrato deste serviço (`edu_common.deps.get_current_user`)
    devolve 403 ("no credential"), não 401 — 401 é só para credencial
    presente e inválida."""
    carrier = await _seed(db_session, name="Y")
    chamadas = [
        ("get", "/carriers", None),
        ("get", f"/carriers/{carrier.id}", None),
        ("post", "/carriers", _PAYLOAD),
        ("put", f"/carriers/{carrier.id}", _PAYLOAD),
        ("patch", f"/carriers/{carrier.id}/status", {"status": "INACTIVE"}),
    ]
    for metodo, url, corpo in chamadas:
        kwargs = {}
        if corpo is not None:
            kwargs["json"] = corpo
        response = await getattr(client, metodo)(url, **kwargs)
        assert response.status_code == 403, f"{metodo} {url} sem credencial"


async def test_listing_is_paginated_and_capped(client):
    response = await client.get("/carriers?limit=5000", headers=headers_for("admin"))
    assert response.status_code == 422


async def test_response_exposes_only_declared_fields(client, db_session):
    await _seed(db_session, name="X")
    row = (await client.get("/carriers", headers=headers_for("admin"))).json()["items"][0]
    assert set(row) == {
        "id",
        "name",
        "location",
        "email",
        "average_delivery_days",
        "rating",
        "sla_percentage",
        "status",
        "created_at",
        "updated_at",
    }


async def test_creating_a_carrier_returns_201_with_the_java_field_shape(client):
    response = await client.post("/carriers", json=_PAYLOAD, headers=headers_for("admin"))
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Rápido Cajamar"
    assert body["average_delivery_days"] == 3
    assert body["rating"] == "4.5"
    assert body["sla_percentage"] == "98.50"
    assert body["status"] == "ACTIVE"


async def test_creating_rejects_a_status_outside_the_enum(client):
    response = await client.post(
        "/carriers", json={**_PAYLOAD, "status": "SUSPENSA"}, headers=headers_for("admin")
    )
    assert response.status_code == 422


async def test_creating_rejects_fields_over_the_java_column_widths(client):
    for campo, valor in (("name", "x" * 151), ("location", "x" * 151)):
        response = await client.post(
            "/carriers", json={**_PAYLOAD, campo: valor}, headers=headers_for("admin")
        )
        assert response.status_code == 422, campo


async def test_rating_and_sla_are_bounded(client):
    fora = [("rating", "6.0"), ("rating", "-1.0"), ("sla_percentage", "101.00")]
    for campo, valor in fora:
        response = await client.post(
            "/carriers", json={**_PAYLOAD, campo: valor}, headers=headers_for("admin")
        )
        assert response.status_code == 422, f"{campo}={valor}"


async def test_search_filters_by_name_and_status_filters_by_state(client, db_session):
    await _seed(db_session, name="Rápido Cajamar", status="ACTIVE")
    await _seed(db_session, name="Lenta Osasco", status="INACTIVE")

    busca = await client.get("/carriers?search=cajamar", headers=headers_for("admin"))
    assert [c["name"] for c in busca.json()["items"]] == ["Rápido Cajamar"]

    inativas = await client.get("/carriers?status=INACTIVE", headers=headers_for("admin"))
    assert [c["name"] for c in inativas.json()["items"]] == ["Lenta Osasco"]


async def test_updating_replaces_every_field(client, db_session):
    carrier = await _seed(db_session, name="Antiga")
    response = await client.put(
        f"/carriers/{carrier.id}",
        json={**_PAYLOAD, "name": "Nova"},
        headers=headers_for("admin"),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Nova"


async def test_status_transition_flips_the_state_and_touches_updated_at(client, db_session):
    carrier = await _seed(db_session, name="X", status="ACTIVE")
    antes = (await client.get(f"/carriers/{carrier.id}", headers=headers_for("admin"))).json()

    response = await client.patch(
        f"/carriers/{carrier.id}/status",
        json={"status": "INACTIVE"},
        headers=headers_for("admin"),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "INACTIVE"
    assert response.json()["updated_at"] >= antes["updated_at"]


async def test_status_transition_rejects_a_value_outside_the_enum(client, db_session):
    carrier = await _seed(db_session, name="X")
    response = await client.patch(
        f"/carriers/{carrier.id}/status",
        json={"status": "SUSPENSA"},
        headers=headers_for("admin"),
    )
    assert response.status_code == 422


async def test_unknown_carrier_is_404_on_every_route(client):
    assert (await client.get("/carriers/999999", headers=headers_for("admin"))).status_code == 404
    assert (
        await client.put("/carriers/999999", json=_PAYLOAD, headers=headers_for("admin"))
    ).status_code == 404
    assert (
        await client.patch(
            "/carriers/999999/status", json={"status": "INACTIVE"}, headers=headers_for("admin")
        )
    ).status_code == 404
