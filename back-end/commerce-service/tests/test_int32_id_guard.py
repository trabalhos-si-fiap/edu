"""Identificador fora de int32 devolve 422, nunca 500.

`Fornecedor.id`, `Estoque.id`, `Carrier.id` e `Ocorrencia.id` são `Integer`
(int32) no Postgres. Um valor fora da faixa atravessa a validação do Pydantic,
chega no asyncpg e levanta `DataError: value out of int32 range` sem
tratamento — 500 onde o contrato deve 422.

A branch da spec B corrigiu esta classe em TRÊS lugares
(`AjusteEstoqueIn.delta`, `ProductIn.quantidade_inicial` e o query param
`partner_id`) e a deixou aberta em oito irmãos. O caso mais afiado: o MESMO
conceito "id de parceiro" estava limitado como query param e ilimitado como
campo de corpo, duas tasks de distância no mesmo serviço.

O alias `app.ids.Int32Id` é a resposta: um tipo com nome, aplicado a todo
site, para não haver uma nona ocorrência. Este arquivo prova a faixa numa
AMOSTRA — uma rota por FORMA de parâmetro (path em dois routers, query,
corpo) e as duas portas que já existiam antes da spec B —, não em todos os
dez sites: o que pode regredir é o alias, e ele é o mesmo objeto em todos.
"""

import uuid
from decimal import Decimal

from edu_common.security import create_access_token

from app.config import settings
from app.models.produto import Estoque, Fornecedor, Product

# 3 bilhões: acima de 2_147_483_647 e abaixo do teto de int64, então o
# Postgres aceitaria a comparação num `bigint` e só recusa por causa da
# coluna. É o valor que reproduziu os 500 nos três sites já corrigidos.
FORA_DE_INT32 = 3_000_000_000


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-0000000000a9") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(sub, role, settings.jwt_secret)}"}


async def test_partner_detail_rejects_an_id_outside_int32(client):
    response = await client.get(f"/partners/{FORA_DE_INT32}", headers=headers_for("admin"))
    assert response.status_code == 422


async def test_carrier_status_rejects_an_id_outside_int32(client):
    response = await client.patch(
        f"/carriers/{FORA_DE_INT32}/status",
        json={"status": "INACTIVE"},
        headers=headers_for("admin"),
    )
    assert response.status_code == 422


async def test_occurrence_list_rejects_a_carrier_filter_outside_int32(client):
    response = await client.get(
        f"/occurrences?carrier_id={FORA_DE_INT32}", headers=headers_for("admin")
    )
    assert response.status_code == 422


async def test_closing_an_occurrence_rejects_an_id_outside_int32(client):
    response = await client.post(
        f"/occurrences/{FORA_DE_INT32}/close",
        json={"observacao": "resolvido"},
        headers=headers_for("admin"),
    )
    assert response.status_code == 422


async def test_opening_a_carrier_occurrence_rejects_a_carrier_id_outside_int32(client):
    """Nono site, achado ao aplicar o alias: `OcorrenciaTransportadoraIn`
    declarava `transportadora_id: int` cru, e `db.get(Carrier, ...)` com valor
    fora da faixa estourava do mesmo jeito. A revisão final listou oito; o
    tipo com nome é o que encontra o nono."""
    response = await client.post(
        "/occurrences/carrier",
        json={
            "pedido_id": str(uuid.uuid4()),
            "transportadora_id": FORA_DE_INT32,
            "tipo": "DANO",
            "motivo": "Caixa amassada",
        },
        headers=headers_for("admin"),
    )
    assert response.status_code == 422


async def test_creating_a_product_rejects_a_supplier_id_outside_int32(client):
    """O caso que nomeia o finding: `partner_id` era limitado como query param
    e `fornecedor_id` ilimitado como campo de corpo."""
    response = await client.post(
        "/products",
        json={
            "name": "Mesa",
            "type": "mobiliario",
            "price": "10.00",
            "sku": "MESA-INT32",
            "fornecedor_id": FORA_DE_INT32,
            "quantidade_inicial": 1,
        },
        headers=headers_for("admin"),
    )
    assert response.status_code == 422


# ── As duas portas anteriores à spec B, incluídas porque o alias as torna
# mudança de uma linha também. ─────────────────────────────────────────────


async def test_occurrence_detail_rejects_an_id_outside_int32(client):
    response = await client.get(f"/occurrences/{FORA_DE_INT32}", headers=headers_for("admin"))
    assert response.status_code == 422


async def test_absolute_stock_adjust_rejects_a_stock_id_outside_int32(client):
    response = await client.patch(
        f"/admin/inventory/{FORA_DE_INT32}/adjust?quantidade=5&motivo=recontagem",
        headers=headers_for("admin"),
    )
    assert response.status_code == 422


# ── A faixa válida continua valendo: o alias não pode transformar um id
# legítimo em 422, nem inventar 404 onde havia 200. ────────────────────────


async def test_a_real_partner_id_still_resolves(client, db_session):
    fornecedor = Fornecedor(nome="Parceiro Teste", origem_rotulo="São Paulo, SP")
    db_session.add(fornecedor)
    await db_session.commit()
    await db_session.refresh(fornecedor)

    response = await client.get(f"/partners/{fornecedor.id}", headers=headers_for("admin"))
    assert response.status_code == 200
    assert response.json()["id"] == fornecedor.id


async def test_a_real_stock_id_still_resolves(client, db_session):
    fornecedor = Fornecedor(nome="Parceiro Estoque", origem_rotulo="São Paulo, SP")
    produto = Product(name="Mesa", type="mobiliario", price=Decimal("10.00"), sku="MESA-OK")
    db_session.add_all([fornecedor, produto])
    await db_session.commit()
    await db_session.refresh(fornecedor)
    await db_session.refresh(produto)
    estoque = Estoque(produto_id=produto.id, fornecedor_id=fornecedor.id, quantidade=10)
    db_session.add(estoque)
    await db_session.commit()
    await db_session.refresh(estoque)

    response = await client.patch(
        f"/admin/inventory/{estoque.id}/adjust?quantidade=5&motivo=recontagem",
        headers=headers_for("admin", sub=str(uuid.uuid4())),
    )
    assert response.status_code == 200
    assert response.json()["quantidade"] == 5
