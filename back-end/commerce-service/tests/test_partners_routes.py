"""Cobertura de `/partners` — o CRUD de parceiro da spec B.

`Fornecedor` é o parceiro; a tabela continua `fornecedores` e a rota é
`/partners` (ver Global Constraints do plano da spec B). Não há entidade
nova.
"""

from decimal import Decimal

import pytest
from edu_common.security import create_access_token

from app.config import settings
from app.models.produto import Fornecedor


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    token = create_access_token(sub, role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


async def _seed_parceiro(db_session, *, nome: str, ativo: bool = True) -> Fornecedor:
    parceiro = Fornecedor(
        nome=nome,
        contato="contato@example.com",
        ativo=ativo,
        origem_rotulo="Cajamar, SP",
        origem_lat=Decimal("-23.355800"),
        origem_lng=Decimal("-46.876400"),
    )
    db_session.add(parceiro)
    await db_session.commit()
    await db_session.refresh(parceiro)
    return parceiro


async def test_listing_requires_authentication(client):
    assert (await client.get("/partners")).status_code == 403


async def test_listing_is_open_to_any_authenticated_role(client, db_session):
    await _seed_parceiro(db_session, nome="Leroy Merlin")
    response = await client.get("/partners", headers=headers_for("student"))
    assert response.status_code == 200
    assert response.json()["total"] == 1


async def test_detail_is_open_to_any_authenticated_role(client, db_session):
    parceiro = await _seed_parceiro(db_session, nome="Leroy Merlin")
    response = await client.get(f"/partners/{parceiro.id}", headers=headers_for("student"))
    assert response.status_code == 200
    assert response.json()["nome"] == "Leroy Merlin"


async def test_listing_is_paginated_and_capped(client):
    assert (
        await client.get("/partners?limit=5000", headers=headers_for("admin"))
    ).status_code == 422


async def test_active_filter_hides_the_disabled_partner(client, db_session):
    await _seed_parceiro(db_session, nome="Leroy Merlin", ativo=True)
    await _seed_parceiro(db_session, nome="Desativada", ativo=False)

    todos = await client.get("/partners", headers=headers_for("student"))
    ativos = await client.get("/partners?active=true", headers=headers_for("student"))

    assert todos.json()["total"] == 2
    assert ativos.json()["total"] == 1
    assert [p["nome"] for p in ativos.json()["items"]] == ["Leroy Merlin"]


async def test_response_exposes_only_declared_fields(client, db_session):
    await _seed_parceiro(db_session, nome="Leroy Merlin")
    row = (await client.get("/partners", headers=headers_for("admin"))).json()["items"][0]
    assert set(row) == {
        "id",
        "nome",
        "contato",
        "ativo",
        "origem_rotulo",
        "origem_lat",
        "origem_lng",
    }


async def test_creating_a_partner_requires_admin(client):
    payload = {"nome": "X", "origem_rotulo": "São Paulo, SP"}
    for papel in ("student", "separador", "entregador"):
        response = await client.post("/partners", json=payload, headers=headers_for(papel))
        assert response.status_code == 403, papel


async def test_updating_a_partner_requires_admin(client, db_session):
    parceiro = await _seed_parceiro(db_session, nome="Leroy Merlin")
    payload = {"nome": "X", "origem_rotulo": "São Paulo, SP"}
    for papel in ("student", "separador", "entregador"):
        response = await client.put(
            f"/partners/{parceiro.id}", json=payload, headers=headers_for(papel)
        )
        assert response.status_code == 403, papel


async def test_admin_creates_a_partner_with_an_origin(client):
    response = await client.post(
        "/partners",
        json={
            "nome": "Leroy Merlin",
            "contato": "parceria@leroymerlin.com.br",
            "ativo": True,
            "origem_rotulo": "Cajamar, SP",
            "origem_lat": "-23.3558",
            "origem_lng": "-46.8764",
        },
        headers=headers_for("admin"),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["origem_rotulo"] == "Cajamar, SP"
    assert body["origem_lat"] == "-23.355800"


async def test_creating_rejects_a_name_over_the_column_width(client):
    response = await client.post(
        "/partners",
        json={"nome": "x" * 151, "origem_rotulo": "São Paulo, SP"},
        headers=headers_for("admin"),
    )
    assert response.status_code == 422


async def test_updating_a_partner_flips_the_active_flag(client, db_session):
    parceiro = await _seed_parceiro(db_session, nome="Leroy Merlin")
    response = await client.put(
        f"/partners/{parceiro.id}",
        json={"nome": "Leroy Merlin", "ativo": False, "origem_rotulo": "Cajamar, SP"},
        headers=headers_for("admin"),
    )
    assert response.status_code == 200
    assert response.json()["ativo"] is False


async def test_updating_an_unknown_partner_is_404(client):
    response = await client.put(
        "/partners/999999",
        json={"nome": "X", "origem_rotulo": "São Paulo, SP"},
        headers=headers_for("admin"),
    )
    assert response.status_code == 404


async def test_detail_of_an_unknown_partner_is_404(client):
    assert (await client.get("/partners/999999", headers=headers_for("admin"))).status_code == 404


@pytest.mark.parametrize("campo", ["origem_lat", "origem_lng"])
async def test_origin_coordinates_are_optional(client, campo):
    payload = {"nome": f"Sem {campo}", "origem_rotulo": "São Paulo, SP"}
    response = await client.post("/partners", json=payload, headers=headers_for("admin"))
    assert response.status_code == 201
    assert response.json()[campo] is None
