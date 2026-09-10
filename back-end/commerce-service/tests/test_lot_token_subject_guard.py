"""Um token de carregamento não é um usuário destas rotas.

`sub` de um token de lote é o id do carregamento — um INTEIRO
(`app/services/carregamentos.py`, decisão D8 do plano: `create_access_token`
não aceita claim extra, então o `sub` *é* o id). Dezoito call sites do
commerce faziam `uuid.UUID(user["sub"])` direto, cada um um `ValueError` não
tratado — 500, não 403 — para esse token. As rotas sem checagem de papel
(`/orders`, `/cart`, `/payment-methods`, o rastreio) são alcançáveis hoje.

Um 500 e um 403 não são a mesma coisa nem para quem opera (um vira alerta de
erro do servidor, o outro é a resposta correta) nem para quem chama.
"""

from edu_common.security import create_access_token

from app.config import settings


def headers_de_lote(carregamento_id: int = 7) -> dict[str, str]:
    token = create_access_token(str(carregamento_id), "carregamento", settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


async def test_a_lot_token_gets_403_on_the_order_list(client):
    response = await client.get("/orders", headers=headers_de_lote())

    assert response.status_code == 403


async def test_a_lot_token_gets_403_on_the_cart(client):
    response = await client.get("/cart", headers=headers_de_lote())

    assert response.status_code == 403


async def test_a_lot_token_gets_403_on_the_payment_methods(client):
    response = await client.get("/payment-methods", headers=headers_de_lote())

    assert response.status_code == 403
