from edu_common.security import create_access_token, hash_password

from app.config import settings
from app.models.user import User


def admin_headers() -> dict[str, str]:
    token = create_access_token(
        "11111111-1111-1111-1111-111111111111", "admin", settings.jwt_secret
    )
    return {"Authorization": f"Bearer {token}"}


def student_headers() -> dict[str, str]:
    token = create_access_token(
        "22222222-2222-2222-2222-222222222222", "student", settings.jwt_secret
    )
    return {"Authorization": f"Bearer {token}"}


async def test_list_users_requires_admin_role(client):
    assert (await client.get("/users", headers=student_headers())).status_code == 403


async def test_list_users_requires_authentication(client):
    assert (await client.get("/users")).status_code == 403


async def test_list_users_is_paginated(client):
    response = await client.get("/users", headers=admin_headers())
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_list_users_rejects_limit_above_the_cap(client):
    response = await client.get("/users?limit=1000", headers=admin_headers())
    assert response.status_code == 422


async def test_list_users_respects_limit(client):
    for i in range(3):
        await client.post(
            "/auth/register",
            json={
                "name": f"User {i}",
                "email": f"u{i}@teste.com",
                "phone": "11999999999",
                "birth_date": "15/06/2005",
                "education_level": "3º ano",
                "password": "Senha@123",
            },
        )
    response = await client.get("/users?limit=2", headers=admin_headers())
    assert len(response.json()) == 2


async def test_list_users_default_limit_caps_an_unbounded_listing(client, db_session):
    """Review finding: no test proved the default (50) actually caps a
    listing left unbounded (no `?limit`) — only that an explicit `?limit=N`
    is respected. Inserted directly via `db_session` (bypassing
    `/auth/register`'s bcrypt hashing 51 times) since this is about the
    listing endpoint's default, not about registration."""
    senha_hash = hash_password("Senha@123")
    for i in range(51):
        db_session.add(
            User(nome=f"Cap {i}", email=f"cap{i}@teste.com", senha_hash=senha_hash, role="student")
        )
    await db_session.commit()

    response = await client.get("/users", headers=admin_headers())

    assert len(response.json()) == 50
