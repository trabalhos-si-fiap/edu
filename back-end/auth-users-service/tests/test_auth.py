"""Testes direcionados às três correções do fix round 1 (não é a suíte de
caracterização completa de /auth/* — essa é da próxima task)."""

import app.routers.auth as auth_module
from tests.helpers import senha_curta_em_caracteres_mas_grande_em_bytes


def _payload_registro_valido(**overrides: str) -> dict:
    payload = {
        "name": "Ana Souza",
        "email": "ana.souza@example.com",
        "phone": "11999999999",
        "birth_date": "15/06/2005",
        "education_level": "3º ano",
        "password": "SenhaForte!1",
    }
    payload.update(overrides)
    return payload


async def test_register_returns_201(client):
    """Prova que o fixture `_stub_publish_event` (Important 4) funciona: sem
    ele, `POST /auth/register` sobe `RuntimeError` do EventPublisher
    desconectado (ASGITransport não roda o lifespan) depois do commit."""
    response = await client.post("/auth/register", json=_payload_registro_valido())

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "ana.souza@example.com"
    assert body["user"]["role"] == "student"
    assert body["tokens"]["access_token"]


async def test_register_rejects_password_over_byte_limit(client):
    """Important 3: uma senha acima de MAX_PASSWORD_BYTES deve ser um 422 de
    validação, não um 500 de `hash_password` levantando ValueError."""
    payload = _payload_registro_valido(password=senha_curta_em_caracteres_mas_grande_em_bytes())

    response = await client.post("/auth/register", json=payload)

    assert response.status_code == 422


async def test_login_with_unknown_email_still_calls_verify_password(client, monkeypatch):
    """Regressão para o Critical 1: `verify_password` tem que rodar mesmo
    quando o e-mail não existe (contra DUMMY_PASSWORD_HASH), ou a defesa
    anti-enumeração volta a ser código morto atrás de um `or` que faz
    short-circuit. Contar chamadas é determinístico; medir tempo de parede
    seria frágil."""
    chamadas = []
    original = auth_module.verify_password

    def verify_com_contagem(plain: str, hashed: str) -> bool:
        chamadas.append(hashed)
        return original(plain, hashed)

    monkeypatch.setattr(auth_module, "verify_password", verify_com_contagem)

    response = await client.post(
        "/auth/login",
        json={"email": "ninguem-com-esse-email@example.com", "password": "qualquer-coisa!1"},
    )

    assert response.status_code == 401
    assert chamadas == [auth_module.DUMMY_PASSWORD_HASH]
