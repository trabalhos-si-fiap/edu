import re

import pytest

from tests.modules.auth.conftest import make_register_payload


@pytest.fixture(autouse=True)
def captured_reset_emails(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Keep the reset flow offline and capture (email, code) the route would enqueue."""
    from app.modules.auth import tasks

    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        tasks.send_password_reset_email_task,
        "delay",
        lambda email, code: calls.append((email, code)),
    )
    return calls


async def _register(client) -> dict:
    payload = make_register_payload()
    resp = await client.post("/api/auth/register", json=payload)
    assert resp.status_code == 201
    return payload


async def test_request_returns_200_for_existing_email_and_enqueues(
    client, captured_reset_emails
) -> None:
    payload = await _register(client)
    resp = await client.post("/api/auth/password-reset/request", json={"email": payload["email"]})
    assert resp.status_code == 200
    assert len(captured_reset_emails) == 1
    assert captured_reset_emails[0][0] == payload["email"]


async def test_request_returns_200_for_unknown_email_without_enqueue(
    client, captured_reset_emails
) -> None:
    resp = await client.post(
        "/api/auth/password-reset/request", json={"email": "nobody@example.com"}
    )
    assert resp.status_code == 200
    assert captured_reset_emails == []


async def test_full_reset_flow_changes_password(client, captured_reset_emails) -> None:
    payload = await _register(client)

    await client.post("/api/auth/password-reset/request", json={"email": payload["email"]})
    _email, code = captured_reset_emails[0]
    assert re.fullmatch(r"\d{6}", code)

    new_password = "Brand!New9"
    confirm = await client.post(
        "/api/auth/password-reset/confirm",
        json={"email": payload["email"], "code": code, "new_password": new_password},
    )
    assert confirm.status_code == 200

    # New password works.
    ok = await client.post(
        "/api/auth/login", json={"email": payload["email"], "password": new_password}
    )
    assert ok.status_code == 200
    # Old password no longer works.
    bad = await client.post(
        "/api/auth/login", json={"email": payload["email"], "password": payload["password"]}
    )
    assert bad.status_code == 401


async def test_confirm_with_wrong_code_is_400(client, captured_reset_emails) -> None:
    payload = await _register(client)
    await client.post("/api/auth/password-reset/request", json={"email": payload["email"]})
    resp = await client.post(
        "/api/auth/password-reset/confirm",
        json={"email": payload["email"], "code": "000000", "new_password": "Brand!New9"},
    )
    assert resp.status_code == 400


async def test_confirm_with_unknown_email_is_400(client) -> None:
    resp = await client.post(
        "/api/auth/password-reset/confirm",
        json={"email": "nobody@example.com", "code": "123456", "new_password": "Brand!New9"},
    )
    assert resp.status_code == 400


async def test_code_is_single_use(client, captured_reset_emails) -> None:
    payload = await _register(client)
    await client.post("/api/auth/password-reset/request", json={"email": payload["email"]})
    _email, code = captured_reset_emails[0]

    first = await client.post(
        "/api/auth/password-reset/confirm",
        json={"email": payload["email"], "code": code, "new_password": "Brand!New9"},
    )
    assert first.status_code == 200
    second = await client.post(
        "/api/auth/password-reset/confirm",
        json={"email": payload["email"], "code": code, "new_password": "Another!9"},
    )
    assert second.status_code == 400
