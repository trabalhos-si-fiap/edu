"""Ajuste de estoque com trilha de auditoria — porte de `InventoryAdjustment`.

O ajuste e o registro acontecem na MESMA transação, sob `with_for_update()`
na linha de estoque (regra 3 do CLAUDE.md). Um ajuste que não deixa rastro é
indistinguível de uma perda de dado.
"""

import asyncio
from decimal import Decimal

from edu_common.security import create_access_token
from sqlalchemy import func, select

from app.config import settings
from app.models.estoque_ajuste import EstoqueAjuste
from app.models.produto import Estoque, Fornecedor, Product

_ADMIN_SUB = "00000000-0000-0000-0000-0000000000aa"


def headers_for(role: str, sub: str = _ADMIN_SUB) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(sub, role, settings.jwt_secret)}"}


async def _seed(db_session, *, quantidade: int = 10) -> tuple[Product, Estoque]:
    fornecedor = Fornecedor(nome="Edu", origem_rotulo="Aclimação, SP")
    db_session.add(fornecedor)
    await db_session.commit()
    await db_session.refresh(fornecedor)

    produto = Product(name="Mesa", type="mobiliario", price=Decimal("399.90"), sku="MESA-1")
    db_session.add(produto)
    await db_session.commit()
    await db_session.refresh(produto)

    estoque = Estoque(
        produto_id=produto.id,
        fornecedor_id=fornecedor.id,
        quantidade=quantidade,
        estoque_minimo=2,
    )
    db_session.add(estoque)
    await db_session.commit()
    await db_session.refresh(estoque)
    return produto, estoque


async def test_adjustment_requires_admin(client, db_session):
    produto, _ = await _seed(db_session)
    for papel in ("student", "separador", "entregador"):
        response = await client.post(
            f"/products/{produto.id}/stock-adjustments",
            json={"delta": 5, "motivo": "Recebimento de lote"},
            headers=headers_for(papel),
        )
        assert response.status_code == 403, papel


async def test_a_positive_delta_moves_the_quantity_and_writes_the_trail(client, db_session):
    produto, estoque = await _seed(db_session, quantidade=10)

    response = await client.post(
        f"/products/{produto.id}/stock-adjustments",
        json={"delta": 5, "motivo": "Recebimento de lote"},
        headers=headers_for("admin"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["quantidade_anterior"] == 10
    assert body["quantidade_nova"] == 15
    assert body["delta"] == 5
    assert body["motivo"] == "Recebimento de lote"
    assert body["autor_id"] == _ADMIN_SUB

    await db_session.refresh(estoque)
    assert estoque.quantidade == 15

    trilha = (await db_session.execute(select(EstoqueAjuste))).scalars().all()
    assert len(trilha) == 1
    assert trilha[0].estoque_id == estoque.id


async def test_a_negative_delta_is_accepted_down_to_zero(client, db_session):
    produto, _estoque = await _seed(db_session, quantidade=3)
    response = await client.post(
        f"/products/{produto.id}/stock-adjustments",
        json={"delta": -3, "motivo": "Perda"},
        headers=headers_for("admin"),
    )
    assert response.status_code == 201
    assert response.json()["quantidade_nova"] == 0


async def test_an_adjustment_that_would_go_negative_is_422_and_writes_nothing(client, db_session):
    """422 DENTRO da transação, sem gravar — nem o estoque nem a trilha.
    Gravar a linha de auditoria de um ajuste recusado seria pior que não
    auditar: a trilha passaria a mentir."""
    produto, estoque = await _seed(db_session, quantidade=3)

    response = await client.post(
        f"/products/{produto.id}/stock-adjustments",
        json={"delta": -4, "motivo": "Perda"},
        headers=headers_for("admin"),
    )

    assert response.status_code == 422
    await db_session.refresh(estoque)
    assert estoque.quantidade == 3
    total = (await db_session.execute(select(func.count()).select_from(EstoqueAjuste))).scalar_one()
    assert total == 0


async def test_a_reason_is_mandatory_and_capped_at_the_column_width(client, db_session):
    produto, _ = await _seed(db_session)
    sem_motivo = await client.post(
        f"/products/{produto.id}/stock-adjustments",
        json={"delta": 1},
        headers=headers_for("admin"),
    )
    assert sem_motivo.status_code == 422

    motivo_gigante = await client.post(
        f"/products/{produto.id}/stock-adjustments",
        json={"delta": 1, "motivo": "x" * 301},
        headers=headers_for("admin"),
    )
    assert motivo_gigante.status_code == 422


async def test_adjusting_an_unstocked_product_is_404(client, db_session):
    produto = Product(name="Sem estoque", type="apostila", price=Decimal("1.00"), sku="X-1")
    db_session.add(produto)
    await db_session.commit()
    await db_session.refresh(produto)

    response = await client.post(
        f"/products/{produto.id}/stock-adjustments",
        json={"delta": 1, "motivo": "Recebimento de lote"},
        headers=headers_for("admin"),
    )
    assert response.status_code == 404


async def test_concurrent_deltas_do_not_lose_an_adjustment(client, db_session):
    """Duas adições simultâneas de +5 sobre 10 têm que dar 20, não 15.

    Sem `with_for_update()` as duas leem 10, as duas gravam 15, e um lote
    inteiro some do sistema sem nenhum erro aparecer. Este é o teste que
    prova a regra 3 do CLAUDE.md nesta rota; ele NÃO é opinião sobre estilo.
    """
    produto, estoque = await _seed(db_session, quantidade=10)

    async def _ajustar():
        return await client.post(
            f"/products/{produto.id}/stock-adjustments",
            json={"delta": 5, "motivo": "Recebimento de lote"},
            headers=headers_for("admin"),
        )

    respostas = await asyncio.gather(_ajustar(), _ajustar())
    assert {r.status_code for r in respostas} == {201}

    await db_session.refresh(estoque)
    assert estoque.quantidade == 20
    total = (await db_session.execute(select(func.count()).select_from(EstoqueAjuste))).scalar_one()
    assert total == 2


async def test_listing_the_trail_is_admin_only_and_paginated(client, db_session):
    produto, _ = await _seed(db_session)
    await client.post(
        f"/products/{produto.id}/stock-adjustments",
        json={"delta": 1, "motivo": "Recebimento de lote"},
        headers=headers_for("admin"),
    )

    negado = await client.get(
        f"/products/{produto.id}/stock-adjustments", headers=headers_for("student")
    )
    assert negado.status_code == 403

    capado = await client.get(
        f"/products/{produto.id}/stock-adjustments?limit=5000", headers=headers_for("admin")
    )
    assert capado.status_code == 422

    ok = await client.get(f"/products/{produto.id}/stock-adjustments", headers=headers_for("admin"))
    assert ok.status_code == 200
    assert ok.json()["total"] == 1


async def test_the_admin_absolute_route_also_writes_the_trail(client, db_session):
    """`PATCH /admin/inventory/{id}/adjust` é a porta ABSOLUTA e a rota nova
    é a porta de DELTA — as duas passam pelo mesmo núcleo, então as duas
    deixam rastro. Antes desta task a rota do admin não deixava nenhum."""
    _, estoque = await _seed(db_session, quantidade=10)

    response = await client.patch(
        f"/admin/inventory/{estoque.id}/adjust?quantidade=4&motivo=Invent%C3%A1rio",
        headers=headers_for("admin"),
    )

    assert response.status_code == 200
    assert response.json()["quantidade"] == 4

    trilha = (await db_session.execute(select(EstoqueAjuste))).scalars().all()
    assert len(trilha) == 1
    assert (trilha[0].quantidade_anterior, trilha[0].quantidade_nova) == (10, 4)
    assert trilha[0].motivo == "Inventário"


async def test_the_admin_absolute_route_also_requires_admin(client, db_session):
    """Fix round 1, finding 1. Esta rota ganhou poder nesta task: agora ela
    AUTORA uma linha de auditoria atribuída a `user["sub"]` — `user` deixou
    de ser um parâmetro só de guarda e passou a ser um valor que o handler
    consome. Se alguém trocar `requer_papel("admin")` por `get_current_user`
    no futuro, o handler continua compilando e a suíte continua verde sem
    este teste, mas qualquer aluno autenticado passaria a reescrever estoque
    e a forjar linhas de auditoria em nome de si mesmo."""
    _, estoque = await _seed(db_session, quantidade=10)

    response = await client.patch(
        f"/admin/inventory/{estoque.id}/adjust?quantidade=4&motivo=Teste",
        headers=headers_for("student"),
    )

    assert response.status_code == 403


async def test_a_delta_out_of_int32_range_is_422_not_500(client, db_session):
    """Fix round 1, finding 2. `Estoque.quantidade` e
    `EstoqueAjuste.quantidade_*` são `Integer` (int32). Sem teto no schema,
    `{"delta": 3000000000, ...}` passava da validação do Pydantic direto para
    o `INSERT` de `estoque_ajustes` e estourava
    `asyncpg.exceptions.DataError: invalid input for query argument ...
    (value out of int32 range)` não tratado — 500, não 422."""
    produto, _ = await _seed(db_session)
    response = await client.post(
        f"/products/{produto.id}/stock-adjustments",
        json={"delta": 3_000_000_000, "motivo": "Recebimento de lote"},
        headers=headers_for("admin"),
    )
    assert response.status_code == 422


async def test_an_absolute_quantity_out_of_int32_range_is_422_not_500(client, db_session):
    """Mesma classe de bug da finding 2, na porta absoluta
    (`PATCH /admin/inventory/{id}/adjust`)."""
    _, estoque = await _seed(db_session, quantidade=10)
    response = await client.patch(
        f"/admin/inventory/{estoque.id}/adjust?quantidade=3000000000&motivo=Teste",
        headers=headers_for("admin"),
    )
    assert response.status_code == 422


async def test_a_whitespace_only_reason_is_rejected_on_the_delta_door(client, db_session):
    """Fix round 1, finding 4. `Field(min_length=1)` só barra string VAZIA —
    `"   "` tem length 3 e passava (o revisor mediu 201). Um motivo feito só
    de espaço em branco é um motivo vazio disfarçado, e uma auditoria sem
    motivo é exatamente o que esta task existe para impedir."""
    produto, _ = await _seed(db_session)
    response = await client.post(
        f"/products/{produto.id}/stock-adjustments",
        json={"delta": 1, "motivo": "   "},
        headers=headers_for("admin"),
    )
    assert response.status_code == 422


async def test_a_whitespace_only_reason_is_rejected_on_the_absolute_door(client, db_session):
    """Mesma classe de bug da finding 4, na porta absoluta."""
    _, estoque = await _seed(db_session, quantidade=10)
    response = await client.patch(
        f"/admin/inventory/{estoque.id}/adjust?quantidade=4&motivo=%20%20%20",
        headers=headers_for("admin"),
    )
    assert response.status_code == 422


async def test_the_absolute_door_also_caps_the_reason_at_the_column_width(client, db_session):
    """Fix round 1, finding 4. O teto de 300 caracteres já funcionava
    (`Query(max_length=300)`), mas só estava pinado por teste na porta de
    delta (`test_a_reason_is_mandatory_and_capped_at_the_column_width`). Sem
    este teste, remover `max_length` desta rota passaria despercebido e um
    motivo de 400 caracteres estouraria em runtime contra o `String(300)` da
    coluna (500), não 422."""
    _, estoque = await _seed(db_session, quantidade=10)
    motivo_gigante = "x" * 400
    response = await client.patch(
        f"/admin/inventory/{estoque.id}/adjust?quantidade=4&motivo={motivo_gigante}",
        headers=headers_for("admin"),
    )
    assert response.status_code == 422


async def test_a_product_stocked_by_two_suppliers_still_resolves_to_one_row(client, db_session):
    """Correção da task 3 ao brief: `Estoque` tem `uq_produto_fornecedor` na
    PAR (produto_id, fornecedor_id), não em `produto_id` sozinho — um
    produto com dois fornecedores gera duas linhas de estoque.
    `obter_estoque_do_produto` filtra só por `produto_id`, então um
    `scalar_one_or_none()` aqui estouraria `MultipleResultsFound` em vez de
    resolver para uma linha. Este teste prova que a rota responde 200 (e não
    500) quando isso acontece.
    """
    fornecedor_a = Fornecedor(nome="Fornecedor A", origem_rotulo="A, SP")
    fornecedor_b = Fornecedor(nome="Fornecedor B", origem_rotulo="B, SP")
    db_session.add_all([fornecedor_a, fornecedor_b])
    await db_session.commit()
    await db_session.refresh(fornecedor_a)
    await db_session.refresh(fornecedor_b)

    produto = Product(name="Cadeira", type="mobiliario", price=Decimal("199.90"), sku="CAD-1")
    db_session.add(produto)
    await db_session.commit()
    await db_session.refresh(produto)

    estoque_a = Estoque(
        produto_id=produto.id,
        fornecedor_id=fornecedor_a.id,
        quantidade=5,
        estoque_minimo=1,
    )
    estoque_b = Estoque(
        produto_id=produto.id,
        fornecedor_id=fornecedor_b.id,
        quantidade=7,
        estoque_minimo=1,
    )
    db_session.add_all([estoque_a, estoque_b])
    await db_session.commit()
    await db_session.refresh(estoque_a)
    await db_session.refresh(estoque_b)

    response = await client.post(
        f"/products/{produto.id}/stock-adjustments",
        json={"delta": 1, "motivo": "Recebimento de lote"},
        headers=headers_for("admin"),
    )

    assert response.status_code == 201
    # Fix round 1, finding 3: o status 201 sozinho não prova QUAL linha se
    # moveu — inverter `order_by(Estoque.id)` para `.desc()` também
    # devolveria 201, só que sobre a linha do fornecedor B. `estoque_a` é a
    # linha mais antiga (id menor), então é ela que `obter_estoque_do_produto`
    # deve resolver.
    assert response.json()["quantidade_anterior"] == 5

    await db_session.refresh(estoque_a)
    await db_session.refresh(estoque_b)
    assert estoque_a.quantidade == 6
    assert estoque_b.quantidade == 7


# ── Revisão final de branch, finding 8 ─────────────────────────────────────


async def test_both_stock_doors_refuse_a_missing_record_in_the_same_language(client, db_session):
    """Duas portas do MESMO núcleo respondiam em idiomas diferentes:
    `POST /products/{id}/stock-adjustments` dizia "Stock record not found" e
    `PATCH /admin/inventory/{id}/adjust` dizia "Registro de estoque não
    encontrado". As duas sentenças chegam ao mesmo usuário brasileiro, pelas
    mesmas duas telas do painel.

    Português é o idioma das mensagens exibíveis desta superfície — é o que a
    mensagem mais escrutinada da branch (`CarrinhoOrigemMistaError.MENSAGEM`)
    já usa e o que os dois clientes mostram."""
    produto, _estoque = await _seed(db_session)
    outro = Product(name="Sem estoque", type="mobiliario", price=Decimal("10.00"), sku="SEM-1")
    db_session.add(outro)
    await db_session.commit()
    await db_session.refresh(outro)
    assert produto.id != outro.id

    porta_delta = await client.post(
        f"/products/{outro.id}/stock-adjustments",
        json={"delta": 5, "motivo": "Recebimento de lote"},
        headers=headers_for("admin"),
    )
    porta_absoluta = await client.patch(
        "/admin/inventory/999999/adjust?quantidade=5&motivo=recontagem",
        headers=headers_for("admin"),
    )

    assert porta_delta.status_code == 404
    assert porta_absoluta.status_code == 404
    assert porta_delta.json()["detail"] == porta_absoluta.json()["detail"]
    assert porta_delta.json()["detail"] == "Registro de estoque não encontrado"
