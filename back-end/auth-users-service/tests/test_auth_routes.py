from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from app.config import settings

REGISTER = {
    "name": "Maria Teste",
    "email": "maria@teste.com",
    "phone": "11999999999",
    "birth_date": "15/06/2005",
    "education_level": "3º ano",
    "password": "Senha@123",
}


async def test_register_creates_user_and_returns_tokens(client):
    response = await client.post("/auth/register", json=REGISTER)
    assert response.status_code == 201
    body = response.json()
    assert body["tokens"]["access_token"]
    assert body["tokens"]["refresh_token"]
    assert body["user"]["email"] == "maria@teste.com"


async def test_register_never_returns_the_password_hash(client):
    body = (await client.post("/auth/register", json=REGISTER)).json()
    assert "senha_hash" not in str(body)
    assert "password" not in body["user"]


async def test_register_rejects_duplicate_email(client):
    await client.post("/auth/register", json=REGISTER)
    response = await client.post("/auth/register", json=REGISTER)
    assert response.status_code == 409


async def test_login_returns_tokens_for_valid_credentials(client):
    await client.post("/auth/register", json=REGISTER)
    response = await client.post(
        "/auth/login", json={"email": REGISTER["email"], "password": REGISTER["password"]}
    )
    assert response.status_code == 200
    assert response.json()["tokens"]["access_token"]


async def test_login_rejects_wrong_password(client):
    await client.post("/auth/register", json=REGISTER)
    response = await client.post(
        "/auth/login", json={"email": REGISTER["email"], "password": "errada"}
    )
    assert response.status_code == 401


async def test_login_rejects_unknown_email_with_same_status(client):
    response = await client.post(
        "/auth/login", json={"email": "ninguem@teste.com", "password": "Senha@123"}
    )
    assert response.status_code == 401


async def test_me_returns_the_authenticated_user(client):
    tokens = (await client.post("/auth/register", json=REGISTER)).json()
    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {tokens['tokens']['access_token']}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == REGISTER["email"]


async def test_me_requires_authentication(client):
    assert (await client.get("/auth/me")).status_code == 403


@pytest.mark.parametrize("token", ["lixo", "a.b.c"])
async def test_me_rejects_invalid_token(client, token):
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_refresh_exchanges_refresh_token_for_new_access_token(client):
    tokens = (await client.post("/auth/register", json=REGISTER)).json()
    response = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["tokens"]["refresh_token"]}
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_refresh_rejects_an_access_token(client):
    tokens = (await client.post("/auth/register", json=REGISTER)).json()
    response = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["tokens"]["access_token"]}
    )
    assert response.status_code == 401


async def test_refresh_rejects_a_validly_signed_token_missing_the_role_claim(client):
    """Additional scope (task 7 review finding, not in the brief): `/auth/refresh`
    read `decoded["sub"]`/`decoded["role"]` unguarded — a validly-signed token
    missing `role` raised `KeyError`, which FastAPI turns into a 500 instead of
    the 401 every other malformed-token path returns."""
    payload = {
        "sub": "33333333-3333-3333-3333-333333333333",
        "type": "refresh",
        "iat": int(datetime.now(UTC).timestamp()),
        "exp": int((datetime.now(UTC) + timedelta(days=7)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    response = await client.post("/auth/refresh", json={"refresh_token": token})

    assert response.status_code == 401
