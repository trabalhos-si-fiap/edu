import re

import pytest
from loguru import logger

REGISTER = {
    "name": "Maria",
    "email": "maria@teste.com",
    "phone": "11999999999",
    "birth_date": "15/06/2005",
    "education_level": "3º ano",
    "password": "Senha@123",
}


@pytest.fixture
def captured_logs():
    messages: list[str] = []
    sink_id = logger.add(lambda message: messages.append(str(message)), level="DEBUG")
    yield messages
    logger.remove(sink_id)


async def test_request_returns_200_for_existing_email(client):
    await client.post("/auth/register", json=REGISTER)
    response = await client.post("/auth/password-reset/request", json={"email": REGISTER["email"]})
    assert response.status_code == 200


async def test_request_returns_200_for_unknown_email_to_prevent_enumeration(client):
    response = await client.post(
        "/auth/password-reset/request", json={"email": "ninguem@teste.com"}
    )
    assert response.status_code == 200


async def test_request_never_returns_the_code(client):
    await client.post("/auth/register", json=REGISTER)
    response = await client.post("/auth/password-reset/request", json={"email": REGISTER["email"]})
    assert "code" not in response.text.lower()


async def test_request_never_logs_the_code(client, captured_logs):
    await client.post("/auth/register", json=REGISTER)
    await client.post("/auth/password-reset/request", json={"email": REGISTER["email"]})
    joined = " ".join(captured_logs)
    assert "código para" not in joined
    assert not re.search(r"\b\d{6}\b", joined), f"código de 6 dígitos vazou no log: {joined}"


async def test_confirm_rejects_wrong_code(client):
    await client.post("/auth/register", json=REGISTER)
    await client.post("/auth/password-reset/request", json={"email": REGISTER["email"]})
    response = await client.post(
        "/auth/password-reset/confirm",
        json={"email": REGISTER["email"], "code": "000000", "new_password": "Nova@123"},
    )
    assert response.status_code == 400


async def test_confirm_rejects_unknown_email_with_the_same_generic_error(client):
    response = await client.post(
        "/auth/password-reset/confirm",
        json={"email": "ninguem@teste.com", "code": "123456", "new_password": "Nova@123"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Código inválido ou expirado"
