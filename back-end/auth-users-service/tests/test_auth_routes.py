import uuid
from datetime import UTC, datetime, timedelta

import pytest
from edu_common.security import create_refresh_token, decode_token
from jose import jwt
from sqlalchemy import select

from app.config import settings
from app.models.user import User

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


async def test_refresh_rejects_a_validly_signed_token_missing_the_sub_claim(client):
    """`/auth/refresh` lia `decoded["sub"]` sem guarda — um token validamente
    assinado sem `sub` levantava `KeyError`, que o FastAPI vira 500 em vez do
    401 que todo outro caminho de token malformado devolve.

    Este teste cobria a claim `role` até a fase 2. Ela deixou de ser exigida
    (o papel passou a vir da coluna), então o que resta a travar aqui é o
    `sub` — sem ele não há usuário para consultar.
    """
    payload = {
        "type": "refresh",
        "iat": int(datetime.now(UTC).timestamp()),
        "exp": int((datetime.now(UTC) + timedelta(days=7)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    response = await client.post("/auth/refresh", json={"refresh_token": token})

    assert response.status_code == 401


async def test_refresh_accepts_a_legacy_token_without_the_role_claim(client, db_session):
    """Mudança de comportamento consciente da fase 2.

    Antes, um refresh token sem `role` era recusado com 401. Agora o papel
    vem da coluna, então esse token funciona e recebe o papel real — que é o
    comportamento certo: a claim antiga não é mais a fonte da verdade.
    """
    registro = await client.post(
        "/auth/register",
        json={
            "name": "Carla",
            "email": "carla.legacy@example.com",
            "phone": "11999999999",
            "birth_date": "15/01/2000",
            "education_level": "3º ano",
            "password": "senha!forte1",
        },
    )
    assert registro.status_code == 201
    user_id = registro.json()["user"]["id"]

    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": int(datetime.now(UTC).timestamp()),
        "exp": int((datetime.now(UTC) + timedelta(days=7)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    response = await client.post("/auth/refresh", json={"refresh_token": token})
    assert response.status_code == 200

    decoded = decode_token(
        response.json()["access_token"],
        settings.jwt_secret,
        settings.jwt_algorithm,
        expected_type="access",
    )
    assert decoded["role"] == "student"


# ── B8: a fixture `_stub_publish_event` descartava o payload, entao nada
# nesta suite via o que `/auth/register` realmente publica — e os dois
# consumidores de `student.created` (learning-service, analytics-service)
# recriavam o formato em literais locais. O router agora monta o payload
# por `edu_common.contracts.StudentCreated`; este teste fixa o formato de
# barramento com LITERAIS (usar `StudentCreated.ROUTING_KEY` ou os nomes
# dos campos aqui faria o teste seguir uma renomeacao em vez de
# detecta-la). ─────────────────────────────────────────────────────────


async def test_register_publishes_the_exact_student_created_payload(client, _stub_publish_event):
    response = await client.post("/auth/register", json=REGISTER)
    assert response.status_code == 201
    user_id = response.json()["user"]["id"]

    publicados = [
        (routing_key, payload)
        for routing_key, payload in _stub_publish_event
        if routing_key == "student.created"
    ]
    assert len(publicados) == 1
    _, payload = publicados[0]

    assert payload == {
        "aluno_id": str(user_id),
        "nome": "Maria Teste",
        "email": "maria@teste.com",
    }


async def test_register_rejects_an_iso_birth_date_with_422(client):
    """`birth_date` em ISO passava pelo validador e estourava no router."""
    response = await client.post(
        "/auth/register",
        json={
            "name": "Ana",
            "email": "ana.iso@example.com",
            "phone": "11999999999",
            "birth_date": "2000-01-15",
            "education_level": "3º ano",
            "password": "senha!forte1",
        },
    )
    assert response.status_code == 422


async def test_register_rejects_an_impossible_date_with_422(client):
    response = await client.post(
        "/auth/register",
        json={
            "name": "Ana",
            "email": "ana.31fev@example.com",
            "phone": "11999999999",
            "birth_date": "31/02/2000",
            "education_level": "3º ano",
            "password": "senha!forte1",
        },
    )
    assert response.status_code == 422


async def test_register_accepts_the_documented_format(client):
    response = await client.post(
        "/auth/register",
        json={
            "name": "Ana",
            "email": "ana.ok@example.com",
            "phone": "11999999999",
            "birth_date": "15/01/2000",
            "education_level": "3º ano",
            "password": "senha!forte1",
        },
    )
    assert response.status_code == 201


async def test_refresh_rejects_a_deactivated_user(client, db_session):
    registro = await client.post(
        "/auth/register",
        json={
            "name": "Ana",
            "email": "ana.deactivate@example.com",
            "phone": "11999999999",
            "birth_date": "15/01/2000",
            "education_level": "3º ano",
            "password": "senha!forte1",
        },
    )
    assert registro.status_code == 201
    refresh_token = registro.json()["tokens"]["refresh_token"]

    result = await db_session.execute(
        select(User).where(User.email == "ana.deactivate@example.com")
    )
    user = result.scalar_one()
    user.ativo = False
    await db_session.commit()

    response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 401


async def test_refresh_reflects_the_current_role(client, db_session):
    """Rebaixar o papel tem que valer no próximo refresh, não só na expiração."""
    registro = await client.post(
        "/auth/register",
        json={
            "name": "Bruno",
            "email": "bruno.role@example.com",
            "phone": "11999999999",
            "birth_date": "15/01/2000",
            "education_level": "3º ano",
            "password": "senha!forte1",
        },
    )
    refresh_token = registro.json()["tokens"]["refresh_token"]

    result = await db_session.execute(select(User).where(User.email == "bruno.role@example.com"))
    user = result.scalar_one()
    user.role = "separador"
    await db_session.commit()

    response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200

    decoded = decode_token(
        response.json()["access_token"],
        settings.jwt_secret,
        settings.jwt_algorithm,
        expected_type="access",
    )
    assert decoded["role"] == "separador"


async def test_refresh_rejects_a_token_for_a_deleted_user(client):
    token = create_refresh_token(
        str(uuid.uuid4()),
        "student",
        settings.jwt_secret,
        settings.jwt_algorithm,
        settings.refresh_token_expire_days,
    )
    response = await client.post("/auth/refresh", json={"refresh_token": token})
    assert response.status_code == 401
