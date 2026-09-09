import time

from edu_common.security import decode_token

from app.config import settings
from app.services.status_pedido import StatusPedido

# Reusa os helpers da task 4 em vez de reescrevê-los.
from tests.test_shipments_routes import _seed_pedido, _seed_transportadora, headers_for


async def _criar_carregamento(client, db_session) -> dict:
    carrier = await _seed_transportadora(db_session)
    return (
        await client.post(
            "/shipments", headers=headers_for("admin"), json={"transportadora_id": carrier.id}
        )
    ).json()


CREDENCIAL = {"nome": "Maria da Silva", "contato": "11999990000"}


async def test_login_with_the_right_credential_returns_a_scoped_token(client, db_session):
    lote = await _criar_carregamento(client, db_session)

    response = await client.post(
        "/shipments/login",
        json={"codigo": lote["codigo"], "senha": lote["senha"], **CREDENCIAL},
    )

    assert response.status_code == 200
    corpo = response.json()
    claims = decode_token(corpo["access_token"], settings.jwt_secret, expected_type="access")
    # O `sub` É o id do lote: `edu_common.security` não aceita claim extra, e
    # esta spec não o altera por causa disso (D8).
    assert claims["sub"] == str(lote["id"])
    assert claims["role"] == "carregamento"


async def test_the_first_access_records_who_took_the_load(client, db_session):
    lote = await _criar_carregamento(client, db_session)

    await client.post(
        "/shipments/login",
        json={"codigo": lote["codigo"], "senha": lote["senha"], **CREDENCIAL},
    )

    detalhe = (await client.get(f"/shipments/{lote['id']}", headers=headers_for("admin"))).json()
    assert detalhe["entregador_nome"] == "Maria da Silva"
    assert detalhe["entregador_contato"] == "11999990000"
    assert detalhe["aberto_em"] is not None


async def test_a_second_access_does_not_rewrite_the_first(client, db_session):
    lote = await _criar_carregamento(client, db_session)
    await client.post(
        "/shipments/login",
        json={"codigo": lote["codigo"], "senha": lote["senha"], **CREDENCIAL},
    )

    await client.post(
        "/shipments/login",
        json={
            "codigo": lote["codigo"],
            "senha": lote["senha"],
            "nome": "Outra Pessoa",
            "contato": "11888880000",
        },
    )

    detalhe = (await client.get(f"/shipments/{lote['id']}", headers=headers_for("admin"))).json()
    assert detalhe["entregador_nome"] == "Maria da Silva"


async def test_a_wrong_password_is_refused(client, db_session):
    lote = await _criar_carregamento(client, db_session)

    response = await client.post(
        "/shipments/login",
        json={"codigo": lote["codigo"], "senha": "SENHAERRADA1", **CREDENCIAL},
    )

    assert response.status_code == 401


async def test_a_wrong_code_answers_exactly_like_a_wrong_password(client, db_session):
    """Mesma resposta e mesmo tempo: um código inexistente não pode ser
    distinguível de uma senha errada, senão o endpoint vira um oráculo de
    quais lotes existem."""
    lote = await _criar_carregamento(client, db_session)

    inicio = time.monotonic()
    codigo_errado = await client.post(
        "/shipments/login",
        json={"codigo": "ZZZZZZZZ", "senha": lote["senha"], **CREDENCIAL},
    )
    tempo_codigo = time.monotonic() - inicio

    inicio = time.monotonic()
    senha_errada = await client.post(
        "/shipments/login",
        json={"codigo": lote["codigo"], "senha": "SENHAERRADA1", **CREDENCIAL},
    )
    tempo_senha = time.monotonic() - inicio

    assert codigo_errado.status_code == senha_errada.status_code == 401
    assert codigo_errado.json()["detail"] == senha_errada.json()["detail"]
    # Os dois caminhos rodam UM bcrypt de custo 12. A folga é larga de
    # propósito: isto é uma trava contra o caminho que retorna cedo sem
    # verificar hash nenhum (que seria ordens de grandeza mais rápido), não
    # uma medição de microbenchmark.
    assert min(tempo_codigo, tempo_senha) > 0.5 * max(tempo_codigo, tempo_senha)


async def test_the_shipment_token_cannot_use_a_staff_route(client, db_session):
    """`requer_papel("separador"|"entregador"|"admin")` continua recusando o
    token de lote: ele não é um usuário."""
    lote = await _criar_carregamento(client, db_session)
    token = (
        await client.post(
            "/shipments/login",
            json={"codigo": lote["codigo"], "senha": lote["senha"], **CREDENCIAL},
        )
    ).json()["access_token"]

    response = await client.get("/picking/queue", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


async def test_the_shipment_token_sees_only_its_own_orders(client, db_session):
    meu = await _criar_carregamento(client, db_session)
    outro = await _criar_carregamento(client, db_session)
    pedido_meu = await _seed_pedido(db_session)
    pedido_alheio = await _seed_pedido(db_session)
    for lote, pedido in ((meu, pedido_meu), (outro, pedido_alheio)):
        await client.post(
            f"/shipments/{lote['id']}/orders",
            headers=headers_for("admin"),
            json={"pedido_id": str(pedido.id)},
        )

    token = (
        await client.post(
            "/shipments/login",
            json={"codigo": meu["codigo"], "senha": meu["senha"], **CREDENCIAL},
        )
    ).json()["access_token"]
    cabecalho = {"Authorization": f"Bearer {token}"}

    fila = await client.get("/delivery/queue", headers=cabecalho)
    assert fila.status_code == 200
    assert [p["id"] for p in fila.json()] == [str(pedido_meu.id)]

    # Pedido REAL de outro lote, não um id inventado: é a diferença entre
    # provar autorização e provar validação de entrada.
    proibido = await client.patch(f"/delivery/{pedido_alheio.id}/collect", headers=cabecalho)
    assert proibido.status_code == 403


async def test_the_shipment_token_can_collect_and_deliver_its_order(client, db_session):
    lote = await _criar_carregamento(client, db_session)
    pedido = await _seed_pedido(db_session)
    await client.post(
        f"/shipments/{lote['id']}/orders",
        headers=headers_for("admin"),
        json={"pedido_id": str(pedido.id)},
    )
    token = (
        await client.post(
            "/shipments/login",
            json={"codigo": lote["codigo"], "senha": lote["senha"], **CREDENCIAL},
        )
    ).json()["access_token"]
    cabecalho = {"Authorization": f"Bearer {token}"}

    coleta = await client.patch(f"/delivery/{pedido.id}/collect", headers=cabecalho)
    entrega = await client.patch(f"/delivery/{pedido.id}/deliver", headers=cabecalho)

    assert (coleta.status_code, entrega.status_code) == (200, 200)
    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.ENTREGUE.value
