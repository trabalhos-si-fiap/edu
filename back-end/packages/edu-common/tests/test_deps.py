from datetime import UTC, datetime, timedelta

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from jose import jwt

from edu_common.deps import build_auth_deps
from edu_common.security import create_access_token, create_refresh_token

SECRET = "test-secret-not-a-real-key"  # noqa: S105 -- test fixture, not a real secret
auth = build_auth_deps(SECRET)


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()

    @application.get("/me")
    async def me(user: dict = Depends(auth.get_current_user)):
        return {"sub": user["sub"], "role": user["role"], "has_raw": bool(user.get("raw_token"))}

    @application.get("/my-id")
    async def my_id(user_id: str = Depends(auth.get_current_user_id)):
        return {"id": user_id}

    @application.get("/raw-token")
    async def raw_token_route(user: dict = Depends(auth.get_current_user)):
        return {"raw_token": user["raw_token"]}

    # `extend-immutable-calls` in pyproject.toml exempts the outer
    # `Depends(...)` call, but not this inner `require_role(...)` factory
    # call: `auth` is a local instance (each service builds its own from
    # `build_auth_deps(...)`), not a stable importable dotted path ruff can
    # match against, so B008 still fires on it. Narrowly suppressed here;
    # every service that calls `require_role("some-role")` inline will hit
    # the same residual case.
    @application.get("/admin-only")
    async def admin_only(user: dict = Depends(auth.require_role("admin"))):  # noqa: B008
        return {"ok": True, "role": user["role"]}

    @application.get("/staff-only")
    async def staff_only(
        user: dict = Depends(auth.require_role("separador", "entregador")),  # noqa: B008
    ):
        return {"ok": True}

    return application


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def forge_token_with_decoy_raw_token_claim(secret: str) -> str:
    """A validly-signed access token whose payload smuggles its own
    `raw_token` claim. Used to prove `get_current_user`'s merge order
    (`{**payload, "raw_token": credentials.credentials}`) always lets the
    real bearer credential win -- reversing that order would let this decoy
    claim leak out as if it were the caller's actual token."""
    now = datetime.now(UTC)
    payload = {
        "sub": "user-1",
        "role": "student",
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "jti": "forged-jti",
        "raw_token": "decoy-value-that-must-not-win",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


async def test_get_current_user_returns_payload(client):
    token = create_access_token("user-1", "student", SECRET)
    response = await client.get("/me", headers=bearer(token))
    assert response.status_code == 200
    assert response.json() == {"sub": "user-1", "role": "student", "has_raw": True}


async def test_get_current_user_id_returns_sub(client):
    token = create_access_token("user-42", "student", SECRET)
    response = await client.get("/my-id", headers=bearer(token))
    assert response.status_code == 200
    assert response.json() == {"id": "user-42"}


async def test_missing_token_is_rejected(client):
    assert (await client.get("/me")).status_code == 403


async def test_invalid_token_is_rejected(client):
    response = await client.get("/me", headers=bearer("nao.e.um.jwt"))
    assert response.status_code == 401


async def test_token_signed_with_other_secret_is_rejected(client):
    token = create_access_token("user-1", "student", "outro-secret")
    assert (await client.get("/me", headers=bearer(token))).status_code == 401


async def test_refresh_token_is_rejected_where_access_is_required(client):
    token = create_refresh_token("user-1", "student", SECRET)
    response = await client.get("/me", headers=bearer(token))
    assert response.status_code == 401


async def test_require_role_allows_matching_role(client):
    token = create_access_token("admin-1", "admin", SECRET)
    response = await client.get("/admin-only", headers=bearer(token))
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


async def test_require_role_forbids_other_role(client):
    token = create_access_token("user-1", "student", SECRET)
    assert (await client.get("/admin-only", headers=bearer(token))).status_code == 403


async def test_require_role_accepts_any_of_several_roles(client):
    for role in ("separador", "entregador"):
        token = create_access_token("staff", role, SECRET)
        assert (await client.get("/staff-only", headers=bearer(token))).status_code == 200


async def test_require_role_still_rejects_invalid_token(client):
    assert (await client.get("/admin-only", headers=bearer("lixo"))).status_code == 401


async def test_raw_token_matches_the_exact_bearer_credential(client):
    token = create_access_token("user-1", "student", SECRET)
    response = await client.get("/raw-token", headers=bearer(token))
    assert response.status_code == 200
    assert response.json()["raw_token"] == token


async def test_raw_token_is_not_shadowed_by_a_payload_claim_of_the_same_name(client):
    forged = forge_token_with_decoy_raw_token_claim(SECRET)
    response = await client.get("/raw-token", headers=bearer(forged))
    assert response.status_code == 200
    assert response.json()["raw_token"] == forged


async def test_basic_scheme_is_rejected(client):
    response = await client.get("/me", headers={"Authorization": "Basic xyz"})
    assert response.status_code == 403


async def test_bearer_with_empty_value_is_rejected(client):
    response = await client.get("/me", headers={"Authorization": "Bearer "})
    assert response.status_code == 403


async def test_bearer_with_whitespace_only_value_is_rejected(client):
    response = await client.get("/me", headers={"Authorization": "Bearer    "})
    assert response.status_code == 403


async def test_bare_bearer_with_no_space_is_rejected(client):
    response = await client.get("/me", headers={"Authorization": "Bearer"})
    assert response.status_code == 403


def test_build_auth_deps_rejects_empty_secret():
    with pytest.raises(ValueError, match="secret"):
        build_auth_deps("")


def test_build_auth_deps_rejects_whitespace_only_secret():
    with pytest.raises(ValueError, match="secret"):
        build_auth_deps("   ")
