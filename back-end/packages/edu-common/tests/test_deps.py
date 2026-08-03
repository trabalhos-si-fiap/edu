import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from edu_common.deps import build_auth_deps
from edu_common.security import create_access_token, create_refresh_token

SECRET = "test-secret-not-a-real-key"  # noqa: S105 -- test fixture, not a real secret
auth = build_auth_deps(SECRET)


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()

    # `Depends(...)` as a default value is FastAPI's own dependency-injection
    # idiom, not the mutable-default footgun B008 guards against. Suppressed
    # below wherever it (or a `require_role(...)` factory call feeding it)
    # appears.
    @application.get("/me")
    async def me(user: dict = Depends(auth.get_current_user)):  # noqa: B008
        return {"sub": user["sub"], "role": user["role"], "has_raw": bool(user.get("raw_token"))}

    @application.get("/my-id")
    async def my_id(user_id: str = Depends(auth.get_current_user_id)):
        return {"id": user_id}

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
