import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.e2e


def _unique_email() -> str:
    return f"e2e-{uuid.uuid4().hex[:10]}@example.local"


def _register_payload(email: str | None = None) -> dict[str, object]:
    return {
        "name": "E2E Tester",
        "email": email or _unique_email(),
        "phone": "(11) 99999-9999",
        "birth_date": "01/01/2000",
        "education_level": "Ensino Superior",
        "password": "E2ePass!9",
    }


async def test_health_is_up(http: AsyncClient) -> None:
    r = await http.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_full_auth_flow(http: AsyncClient) -> None:
    payload = _register_payload()

    r = await http.post("/api/auth/register", json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user"]["email"] == payload["email"]
    assert body["user"]["phone"] == "11999999999"  # normalized digits-only
    assert "password_hash" not in body["user"]
    assert "password" not in body["user"]
    refresh_token = body["tokens"]["refresh_token"]

    r = await http.post(
        "/api/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert r.status_code == 200, r.text
    access_token = r.json()["tokens"]["access_token"]

    r = await http.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert r.status_code == 200
    assert r.json()["email"] == payload["email"]

    r = await http.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 200
    rotated = r.json()
    assert rotated["access_token"] and rotated["refresh_token"]
    assert rotated["token_type"] == "bearer"

    r = await http.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {rotated['access_token']}"},
    )
    assert r.status_code == 200
    assert r.json() == {"detail": "ok"}


async def test_duplicate_email_returns_409(http: AsyncClient) -> None:
    payload = _register_payload()
    r = await http.post("/api/auth/register", json=payload)
    assert r.status_code == 201
    r = await http.post("/api/auth/register", json=payload)
    assert r.status_code == 409


async def test_wrong_password_returns_401(http: AsyncClient) -> None:
    payload = _register_payload()
    await http.post("/api/auth/register", json=payload)
    r = await http.post(
        "/api/auth/login",
        json={"email": payload["email"], "password": "WrongPass!9"},
    )
    assert r.status_code == 401


async def test_access_token_cannot_be_used_as_refresh(http: AsyncClient) -> None:
    payload = _register_payload()
    body = (await http.post("/api/auth/register", json=payload)).json()
    access = body["tokens"]["access_token"]
    r = await http.post("/api/auth/refresh", json={"refresh_token": access})
    assert r.status_code == 401


async def test_login_rate_limit_eventually_triggers_429(http: AsyncClient) -> None:
    # Use a fresh email so we don't collide with other tests' email counters.
    payload = _register_payload()
    await http.post("/api/auth/register", json=payload)

    saw_429 = False
    for _ in range(10):
        r = await http.post(
            "/api/auth/login",
            json={"email": payload["email"], "password": "WrongPass!9"},
        )
        if r.status_code == 429:
            assert int(r.headers["retry-after"]) > 0
            saw_429 = True
            break
        assert r.status_code == 401
    assert saw_429, "login endpoint did not enforce the rate limit within 10 attempts"
