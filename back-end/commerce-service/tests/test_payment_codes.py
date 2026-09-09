"""Paridade dos códigos de pagamento com o mock do cliente que eles substituem.

NÃO É INTEGRAÇÃO COM PROVEDOR. É o mesmo algoritmo que rodava no app,
movido para onde o dado nasce. Isso está dito aqui, no docstring do serviço,
e no relatório final da entrega, para ninguém ler como pagamento real.

Paridade ESTRUTURAL, não byte a byte, e o motivo é medido: o cliente
(`checkout_screen.dart::_generatePixCode`) sorteia o `txid` com `Random()` e
NÃO produz o mesmo payload duas vezes para o mesmo pedido. "Idêntico" não
pode ser literal. O que era contrato de verdade — template EMV, segmentos
fixos, alfabeto e comprimento do txid, comprimento total — é o que este
arquivo trava. A aleatoriedade era acidente do mock.

O backend deriva o txid do `order_id`, então o mesmo pedido devolve sempre o
mesmo código: o aluno pode reabrir a tela sem receber um código diferente do
que já copiou.
"""

import re
import uuid

from edu_common.security import create_access_token

from app.config import settings
from app.services.codigos_pagamento import (
    PIX_PREFIXO,
    PIX_SUFIXO,
    TXID_ALFABETO,
    gerar_codigo_pagamento,
    gerar_codigo_pix,
    gerar_linha_digitavel,
)

_PEDIDO = uuid.UUID("0198f3a1-0000-7000-8000-000000000001")


def test_the_pix_payload_keeps_the_client_template():
    codigo = gerar_codigo_pix(_PEDIDO)
    assert codigo.startswith(PIX_PREFIXO)
    assert codigo.endswith(PIX_SUFIXO)
    assert len(codigo) == len(PIX_PREFIXO) + 25 + len(PIX_SUFIXO)


def test_the_txid_uses_the_client_alphabet_and_length():
    txid = gerar_codigo_pix(_PEDIDO)[len(PIX_PREFIXO) : -len(PIX_SUFIXO)]
    assert len(txid) == 25
    assert set(txid) <= set(TXID_ALFABETO)


def test_the_pix_payload_is_deterministic_per_order():
    assert gerar_codigo_pix(_PEDIDO) == gerar_codigo_pix(_PEDIDO)


def test_two_orders_get_two_payloads():
    outro = uuid.UUID("0198f3a1-0000-7000-8000-000000000002")
    assert gerar_codigo_pix(_PEDIDO) != gerar_codigo_pix(outro)


def test_the_boleto_line_keeps_the_client_grouping():
    linha = gerar_linha_digitavel(_PEDIDO)
    assert re.fullmatch(r"\d{5}\.\d{5} \d{5}\.\d{6} \d{5}\.\d{6} \d \d{14}", linha)
    assert len(linha.replace(".", "").replace(" ", "")) == 47


def test_the_boleto_line_is_deterministic_per_order():
    assert gerar_linha_digitavel(_PEDIDO) == gerar_linha_digitavel(_PEDIDO)


def test_the_dispatcher_picks_by_payment_method_label():
    """O rótulo vem do app ("PIX", "Boleto", "Visa ••••1234") — é o que
    `orders.payment_method` guarda. Cartão não tem código para copiar."""
    assert gerar_codigo_pagamento(_PEDIDO, "PIX").startswith(PIX_PREFIXO)
    assert gerar_codigo_pagamento(_PEDIDO, "pix").startswith(PIX_PREFIXO)
    assert " " in gerar_codigo_pagamento(_PEDIDO, "Boleto")
    assert gerar_codigo_pagamento(_PEDIDO, "Visa ••••1234") is None
    assert gerar_codigo_pagamento(_PEDIDO, "") is None


def headers_for(sub: str, role: str = "student") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(sub, role, settings.jwt_secret)}"}


async def _pedido_do_aluno(client, aluno: str, db_session, metodo: str = "PIX") -> str:
    from decimal import Decimal

    from app.models.produto import Product

    produto = Product(name="Apostila", type="apostila", price=Decimal("10.00"), sku="AP-1")
    db_session.add(produto)
    await db_session.commit()
    await db_session.refresh(produto)

    await client.post(
        "/cart/items",
        json={"product_id": str(produto.id), "quantity": 1},
        headers=headers_for(aluno),
    )
    criado = await client.post(
        "/orders", json={"payment_method": metodo}, headers=headers_for(aluno)
    )
    return criado.json()["id"]


async def test_confirm_payment_returns_the_code_to_the_owner(client, db_session):
    aluno = "00000000-0000-0000-0000-0000000000dd"
    order_id = await _pedido_do_aluno(client, aluno, db_session)

    response = await client.post(f"/orders/{order_id}/confirm-payment", headers=headers_for(aluno))

    assert response.status_code == 200
    body = response.json()
    assert body["payment_method"] == "PIX"
    assert body["payment_code"].startswith(PIX_PREFIXO)


async def test_confirm_payment_is_idempotent(client, db_session):
    aluno = "00000000-0000-0000-0000-0000000000de"
    order_id = await _pedido_do_aluno(client, aluno, db_session)
    primeira = await client.post(f"/orders/{order_id}/confirm-payment", headers=headers_for(aluno))
    segunda = await client.post(f"/orders/{order_id}/confirm-payment", headers=headers_for(aluno))
    assert primeira.json() == segunda.json()


async def test_confirm_payment_does_not_move_the_order_status(client, db_session):
    """Esta rota NÃO é a do admin. `PATCH /admin/orders/{id}/confirm-payment`
    faz CRIADO -> CONFIRMADO -> AGUARDANDO_SEPARACAO; esta só emite o código.
    Duas rotas com nome parecido e donos diferentes — a colisão é de nome,
    não de comportamento."""
    from sqlalchemy import select

    from app.models.pedido import Order
    from app.services.status_pedido import StatusPedido

    aluno = "00000000-0000-0000-0000-0000000000df"
    order_id = await _pedido_do_aluno(client, aluno, db_session)
    await client.post(f"/orders/{order_id}/confirm-payment", headers=headers_for(aluno))

    pedido = (
        await db_session.execute(select(Order).where(Order.id == uuid.UUID(order_id)))
    ).scalar_one()
    assert pedido.status == StatusPedido.CRIADO.value


async def test_confirm_payment_of_someone_else_order_is_404(client, db_session):
    dono = "00000000-0000-0000-0000-0000000000e1"
    order_id = await _pedido_do_aluno(client, dono, db_session)
    alheio = "00000000-0000-0000-0000-0000000000e2"

    response = await client.post(f"/orders/{order_id}/confirm-payment", headers=headers_for(alheio))
    assert response.status_code == 404


async def test_confirm_payment_of_a_card_order_has_no_code(client, db_session):
    aluno = "00000000-0000-0000-0000-0000000000e3"
    order_id = await _pedido_do_aluno(client, aluno, db_session, metodo="Visa ••••1234")
    response = await client.post(f"/orders/{order_id}/confirm-payment", headers=headers_for(aluno))
    assert response.status_code == 200
    assert response.json()["payment_code"] is None


async def test_confirm_payment_requires_authentication(client):
    """Sem credencial nenhuma é 403, não 401 — `edu_common/deps.py` reserva
    401 para credencial presente mas inválida/expirada (`get_current_user`,
    ramo `credentials is None`). O brief desta task mediu 401 aqui; medido de
    novo contra `edu_common/deps.py` (2026-09-09) e é 403. Mesmo
    comportamento que qualquer outra rota deste router sem header
    `Authorization`."""
    response = await client.post("/orders/00000000-0000-0000-0000-0000000000ff/confirm-payment")
    assert response.status_code == 403


async def test_confirm_payment_of_a_non_student_role_is_404_not_a_bypass(client, db_session):
    """Esta rota não tem `requer_papel("student")` — mesmo idioma das outras
    rotas de `pedidos.py` (`listar_pedidos`, `detalhe_pedido`, `recomprar`):
    o controle de acesso vem do FILTRO POR DONO em `services.buscar_pedido`,
    não de um gate de papel. Um staff/admin autenticado com o PRÓPRIO token
    não é dono do pedido do aluno, então cai no mesmo 404 que um aluno
    alheio — a ausência de gate de papel não é um buraco, porque nenhum
    papel além do dono passa pelo filtro de `user_id`."""
    aluno = "00000000-0000-0000-0000-0000000000e4"
    order_id = await _pedido_do_aluno(client, aluno, db_session)

    staff_id = "00000000-0000-0000-0000-0000000000e5"
    response = await client.post(
        f"/orders/{order_id}/confirm-payment", headers=headers_for(staff_id, role="staff")
    )
    assert response.status_code == 404
