import uuid

from edu_common.security import create_access_token
from httpx import AsyncClient

from app.config import settings


class TestAuthRequired:
    async def test_list_requires_auth(self, client: AsyncClient) -> None:
        r = await client.get("/support")
        # 403, não 401: `edu-common` responde 403 para header ausente e 401 para
        # token inválido/expirado; o legacy responde 401 nos dois. Divergência
        # registrada na task B0 do plano do bloco B.
        assert r.status_code == 403

    async def test_send_requires_auth(self, client: AsyncClient) -> None:
        r = await client.post("/support", json={"body": "olá"})
        # 403, não 401: `edu-common` responde 403 para header ausente e 401 para
        # token inválido/expirado; o legacy responde 401 nos dois. Divergência
        # registrada na task B0 do plano do bloco B.
        assert r.status_code == 403


class TestSupportFlow:
    async def test_empty_history(self, client: AsyncClient, auth_headers: dict[str, str]) -> None:
        r = await client.get("/support", headers=auth_headers)
        assert r.status_code == 200, r.text
        assert r.json() == []

    async def test_send_returns_updated_list(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.post("/support", json={"body": "Não consigo pagar"}, headers=auth_headers)
        assert r.status_code == 201, r.text
        body = r.json()
        assert len(body) == 1
        assert body[0]["body"] == "Não consigo pagar"
        assert body[0]["sender"] == "user"
        assert "id" in body[0]
        assert "created_at" in body[0]

    async def test_messages_accumulate_in_order(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        await client.post("/support", json={"body": "primeira"}, headers=auth_headers)
        r = await client.post("/support", json={"body": "segunda"}, headers=auth_headers)
        bodies = [m["body"] for m in r.json()]
        assert bodies == ["primeira", "segunda"]

    async def test_empty_body_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.post("/support", json={"body": ""}, headers=auth_headers)
        assert r.status_code == 422

    async def test_a_body_over_the_cap_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.post("/support", json={"body": "x" * 2001}, headers=auth_headers)
        assert r.status_code == 422


def _headers_de_outro_aluno() -> dict[str, str]:
    """Um segundo aluno, com `sub` diferente do da fixture `student_identity`.

    `user_id` é FK lógica para outro banco: nada no schema impede ler a
    conversa alheia, só a cláusula `where` do serviço. Este teste é o que
    trava essa cláusula.
    """
    token = create_access_token(
        sub=str(uuid.uuid4()),
        role="student",
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


async def test_a_student_never_sees_another_students_conversation(client, student_identity):
    """Porte de `test_messages_are_per_user` do legacy, reescrito: lá o segundo
    aluno vem de `auth_services.register` (banco de usuários local); aqui não
    há tabela de usuários neste serviço, então o segundo aluno vem de um JWT
    minerado com um `sub` novo."""
    await client.post("/support", json={"body": "minha mensagem"}, headers=student_identity.headers)

    resposta = await client.get("/support", headers=_headers_de_outro_aluno())
    assert resposta.status_code == 200
    assert resposta.json() == []
