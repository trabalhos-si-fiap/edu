"""CRUD de produto para o painel. Ver decisão D1 do plano da spec B.

O `product-form-modal` do web-admin cria produto com `sku`, `minimumStock`,
`initialQuantity` e `active`; o backend só tinha GET. O critério de pronto 2
da spec diz "web-admin opera produtos".

`POST /products` cria o produto E a linha de estoque no mesmo ato — a spec
exige que todo produto tenha estoque e todo estoque tenha fornecedor, porque
é isso que elimina o caminho especial de "produto sem parceiro".
"""

from decimal import Decimal

from edu_common.security import create_access_token
from sqlalchemy import select

from app.config import settings
from app.models.produto import Estoque, Fornecedor, Product


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(sub, role, settings.jwt_secret)}"}


async def _seed_parceiro(db_session, nome: str = "Edu") -> Fornecedor:
    parceiro = Fornecedor(nome=nome, origem_rotulo="Aclimação, SP")
    db_session.add(parceiro)
    await db_session.commit()
    await db_session.refresh(parceiro)
    return parceiro


def _payload(fornecedor_id: int, **overrides) -> dict:
    base = {
        "name": "Mesa de estudo",
        "type": "mobiliario",
        "subtype": "Mesa",
        "description": "Tampo de 120 cm",
        "price": "399.90",
        "sku": "LM-MESA-120",
        "active": True,
        "fornecedor_id": fornecedor_id,
        "quantidade_inicial": 12,
        "estoque_minimo": 3,
    }
    base.update(overrides)
    return base


_PUT_PAYLOAD = {
    "name": "N",
    "type": "t",
    "subtype": "",
    "description": "",
    "price": "1.00",
    "sku": "X-1",
    "active": True,
}


async def test_every_admin_product_route_rejects_the_wrong_role(client, db_session):
    """Ruling 6: uma negativa por rota, não uma por grupo — mesma forma de
    `tests/test_carriers_routes.py::test_every_carrier_route_is_admin_only`."""
    parceiro = await _seed_parceiro(db_session)
    chamadas = [
        ("post", "/products", _payload(parceiro.id)),
        ("put", "/products/00000000-0000-0000-0000-0000000000ff", _PUT_PAYLOAD),
    ]
    for metodo, url, corpo in chamadas:
        for papel in ("student", "separador", "entregador"):
            response = await getattr(client, metodo)(url, json=corpo, headers=headers_for(papel))
            assert response.status_code == 403, f"{metodo} {url} {papel}"


async def test_every_admin_product_route_requires_a_credential(client, db_session):
    """Ruling 3: uma negativa por rota, não uma por grupo. Sem
    `Authorization`, o contrato deste serviço (`edu_common.deps.get_current_user`)
    devolve 403 ("no credential"), não 401 — 401 é só para credencial
    presente e inválida."""
    parceiro = await _seed_parceiro(db_session)
    chamadas = [
        ("post", "/products", _payload(parceiro.id)),
        ("put", "/products/00000000-0000-0000-0000-0000000000ff", _PUT_PAYLOAD),
    ]
    for metodo, url, corpo in chamadas:
        response = await getattr(client, metodo)(url, json=corpo)
        assert response.status_code == 403, f"{metodo} {url} sem credencial"


async def test_admin_creates_a_product_with_its_stock_row(client, db_session):
    parceiro = await _seed_parceiro(db_session)

    response = await client.post(
        "/products", json=_payload(parceiro.id), headers=headers_for("admin")
    )

    assert response.status_code == 201
    body = response.json()
    assert body["sku"] == "LM-MESA-120"
    assert body["active"] is True
    assert body["price"] == "399.90"

    estoque = (await db_session.execute(select(Estoque))).scalars().all()
    assert len(estoque) == 1
    assert estoque[0].fornecedor_id == parceiro.id
    assert estoque[0].quantidade == 12
    assert estoque[0].estoque_minimo == 3


async def test_creating_against_an_unknown_partner_is_404(client):
    response = await client.post("/products", json=_payload(999999), headers=headers_for("admin"))
    assert response.status_code == 404


async def test_a_duplicate_sku_is_409(client, db_session):
    parceiro = await _seed_parceiro(db_session)
    await client.post("/products", json=_payload(parceiro.id), headers=headers_for("admin"))
    de_novo = await client.post(
        "/products", json=_payload(parceiro.id, name="Outra"), headers=headers_for("admin")
    )
    assert de_novo.status_code == 409


async def test_an_empty_sku_is_rejected_on_create(client, db_session):
    """O índice de unicidade é PARCIAL (`WHERE sku <> ''`) para não quebrar
    nos seis produtos já semeados sem sku. Isso significa que o banco aceita
    N produtos com sku vazio — então o VALIDADOR é quem impede um produto novo
    de nascer sem sku."""
    parceiro = await _seed_parceiro(db_session)
    response = await client.post(
        "/products", json=_payload(parceiro.id, sku=""), headers=headers_for("admin")
    )
    assert response.status_code == 422


async def test_two_products_with_an_empty_sku_both_save(client, db_session):
    """O índice é PARCIAL — dois produtos com sku vazio no BANCO (fora do
    validador do POST, ex.: seed) são legais e ambos devem persistir."""
    p1 = Product(name="Legado 1", type="apostila", price=Decimal("10.00"), sku="")
    p2 = Product(name="Legado 2", type="apostila", price=Decimal("10.00"), sku="")
    db_session.add_all([p1, p2])
    await db_session.commit()

    rows = (await db_session.execute(select(Product).where(Product.sku == ""))).scalars().all()
    assert len(rows) == 2


async def test_creating_rejects_fields_over_the_column_widths(client, db_session):
    parceiro = await _seed_parceiro(db_session)
    for campo, valor in (("name", "x" * 161), ("sku", "x" * 61), ("type", "x" * 65)):
        response = await client.post(
            "/products", json=_payload(parceiro.id, **{campo: valor}), headers=headers_for("admin")
        )
        assert response.status_code == 422, campo


async def test_updating_replaces_the_catalog_fields_and_can_deactivate(client, db_session):
    parceiro = await _seed_parceiro(db_session)
    criado = await client.post(
        "/products", json=_payload(parceiro.id), headers=headers_for("admin")
    )
    product_id = criado.json()["id"]

    response = await client.put(
        f"/products/{product_id}",
        json={
            "name": "Mesa de estudo compacta",
            "type": "mobiliario",
            "subtype": "Mesa",
            "description": "Tampo de 90 cm",
            "price": "349.90",
            "sku": "LM-MESA-120",
            "active": False,
        },
        headers=headers_for("admin"),
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Mesa de estudo compacta"
    assert response.json()["active"] is False


async def test_updating_does_not_touch_the_stock_row(client, db_session):
    """Estoque muda por ajuste auditado (`POST .../stock-adjustments`), nunca
    por edição de catálogo. Um PUT de produto que mexesse na quantidade
    contornaria a trilha de auditoria que a task 3 existe para garantir."""
    parceiro = await _seed_parceiro(db_session)
    criado = await client.post(
        "/products", json=_payload(parceiro.id), headers=headers_for("admin")
    )
    await client.put(
        f"/products/{criado.json()['id']}",
        json={
            "name": "N",
            "type": "mobiliario",
            "subtype": "",
            "description": "",
            "price": "1.00",
            "sku": "LM-MESA-120",
            "active": True,
        },
        headers=headers_for("admin"),
    )
    estoque = (await db_session.execute(select(Estoque))).scalars().all()
    assert estoque[0].quantidade == 12


async def test_updating_an_unknown_product_is_404(client):
    response = await client.put(
        "/products/00000000-0000-0000-0000-0000000000ff",
        json={
            "name": "N",
            "type": "t",
            "subtype": "",
            "description": "",
            "price": "1.00",
            "sku": "X-1",
            "active": True,
        },
        headers=headers_for("admin"),
    )
    assert response.status_code == 404


async def test_updating_to_a_sku_already_used_by_another_product_is_409(client, db_session):
    parceiro = await _seed_parceiro(db_session)
    primeiro = await client.post(
        "/products", json=_payload(parceiro.id, sku="SKU-A"), headers=headers_for("admin")
    )
    segundo = await client.post(
        "/products",
        json=_payload(parceiro.id, sku="SKU-B", name="Outra"),
        headers=headers_for("admin"),
    )

    response = await client.put(
        f"/products/{segundo.json()['id']}",
        json={
            "name": "Outra",
            "type": "mobiliario",
            "subtype": "",
            "description": "",
            "price": "1.00",
            "sku": "SKU-A",
            "active": True,
        },
        headers=headers_for("admin"),
    )
    assert response.status_code == 409
    assert primeiro.status_code == 201


async def test_the_public_listing_exposes_sku_and_active(client, db_session):
    parceiro = await _seed_parceiro(db_session)
    await client.post("/products", json=_payload(parceiro.id), headers=headers_for("admin"))
    row = (await client.get("/products", headers=headers_for("student"))).json()["items"][0]
    assert row["sku"] == "LM-MESA-120"
    assert row["active"] is True
