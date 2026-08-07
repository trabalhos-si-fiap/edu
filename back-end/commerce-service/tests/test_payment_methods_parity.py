"""Testes de paridade de `/payment-methods` — porte de
`legacy/tests/modules/payment_methods/test_routes.py` (task B9 do bloco B).
Ver `task-B9-report.md` para a lista completa de asserções adaptadas e para
as provas de ownership e de mutação que este arquivo acrescenta (o legacy
não tem nenhuma das duas).

Divergência de contrato herdada de B0/B6/B8: header ausente devolve 403 no
commerce (`edu-common`), não 401 como no legacy — só 1 asserção deste
arquivo muda por causa disso (`TestAuthRequired.test_list_requires_auth`).
"""

import uuid

import pytest
from edu_common.security import create_access_token
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.pagamento import PaymentMethod

STUDENT_A = "00000000-0000-0000-0000-0000000000a1"
STUDENT_B = "00000000-0000-0000-0000-0000000000b2"


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    token = create_access_token(sub, role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


def credit_card(**overrides: object) -> dict[str, object]:
    """Porte de `legacy/tests/modules/payment_methods/conftest.py::credit_card`."""
    base: dict[str, object] = {
        "type": "credit_card",
        "card_last4": "1234",
        "card_brand": "Visa",
        "cardholder_name": "Maria Silva",
        "card_expiry": "1230",
    }
    base.update(overrides)
    return base


def pix(**overrides: object) -> dict[str, object]:
    """Porte de `legacy/tests/modules/payment_methods/conftest.py::pix`."""
    base: dict[str, object] = {"type": "pix"}
    base.update(overrides)
    return base


class TestAuthRequired:
    async def test_list_requires_auth(self, client: AsyncClient) -> None:
        r = await client.get("/payment-methods")
        # 403, não 401: divergência medida na task B0 (edu-common responde
        # 403 para header ausente, 401 para token inválido/expirado; o
        # legacy responde 401 nos dois). Esta é a 1 das N=5 asserções
        # citadas pelo CONTEXTO DO CONTROLADOR do brief.
        assert r.status_code == 403


class TestPciSafety:
    async def test_full_card_number_is_rejected(self, client: AsyncClient) -> None:
        # Um cliente nunca deve mandar o PAN completo; campo extra é proibido.
        payload = credit_card(card_number="4111111111111111")
        r = await client.post("/payment-methods", json=payload, headers=headers_for("student"))
        assert r.status_code == 422

    async def test_cvv_is_rejected(self, client: AsyncClient) -> None:
        payload = credit_card(cvv="123")
        r = await client.post("/payment-methods", json=payload, headers=headers_for("student"))
        assert r.status_code == 422

    async def test_card_last4_must_be_four_digits(self, client: AsyncClient) -> None:
        r = await client.post(
            "/payment-methods",
            json=credit_card(card_last4="4111111111111111"),
            headers=headers_for("student"),
        )
        assert r.status_code == 422

    async def test_stored_method_never_exposes_secret_fields(self, client: AsyncClient) -> None:
        r = await client.post(
            "/payment-methods", json=credit_card(), headers=headers_for("student")
        )
        body = r.json()
        for forbidden in ("card_number", "pan", "cvv", "cardholder_tax_id"):
            assert forbidden not in body
        assert body["card_last4"] == "1234"


class TestCreate:
    async def test_first_method_is_default(self, client: AsyncClient) -> None:
        r = await client.post(
            "/payment-methods", json=credit_card(), headers=headers_for("student")
        )
        assert r.status_code == 201, r.text
        assert r.json()["is_default"] is True

    async def test_credit_card_missing_fields_returns_422(self, client: AsyncClient) -> None:
        r = await client.post(
            "/payment-methods",
            json={"type": "credit_card", "card_last4": "1234"},
            headers=headers_for("student"),
        )
        assert r.status_code == 422

    async def test_pix_happy_path(self, client: AsyncClient) -> None:
        # PIX não guarda dado nenhum — o código de pagamento é gerado no checkout.
        r = await client.post("/payment-methods", json=pix(), headers=headers_for("student"))
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["type"] == "pix"
        assert body["pix_key"] is None

    async def test_second_default_unsets_first(self, client: AsyncClient) -> None:
        first = (
            await client.post(
                "/payment-methods", json=credit_card(), headers=headers_for("student")
            )
        ).json()
        await client.post(
            "/payment-methods", json=pix(is_default=True), headers=headers_for("student")
        )
        listing = (await client.get("/payment-methods", headers=headers_for("student"))).json()
        defaults = [m for m in listing if m["is_default"]]
        assert len(defaults) == 1
        assert defaults[0]["type"] == "pix"
        first_now = next(m for m in listing if m["id"] == first["id"])
        assert first_now["is_default"] is False


class TestSetDefaultAndDelete:
    async def test_patch_sets_default(self, client: AsyncClient) -> None:
        await client.post("/payment-methods", json=credit_card(), headers=headers_for("student"))
        second = (
            await client.post("/payment-methods", json=pix(), headers=headers_for("student"))
        ).json()

        r = await client.patch(
            f"/payment-methods/{second['id']}",
            json={"is_default": True},
            headers=headers_for("student"),
        )
        assert r.status_code == 200
        assert r.json()["is_default"] is True

    async def test_delete_promotes_remaining_to_default(self, client: AsyncClient) -> None:
        first = (
            await client.post(
                "/payment-methods", json=credit_card(), headers=headers_for("student")
            )
        ).json()  # default
        second = (
            await client.post("/payment-methods", json=pix(), headers=headers_for("student"))
        ).json()

        r = await client.delete(f"/payment-methods/{first['id']}", headers=headers_for("student"))
        assert r.status_code == 204

        listing = (await client.get("/payment-methods", headers=headers_for("student"))).json()
        assert len(listing) == 1
        assert listing[0]["id"] == second["id"]
        assert listing[0]["is_default"] is True

    async def test_delete_unknown_returns_404(self, client: AsyncClient) -> None:
        r = await client.delete(f"/payment-methods/{uuid.uuid4()}", headers=headers_for("student"))
        assert r.status_code == 404


class TestBareArrayContract:
    """Acréscimo da B9 — item 7 da tabela de "comportamentos preservados":
    `GET` devolve array puro, sem envelope, ao contrário de `/products`
    (`ProductList`: `items`/`total`/`limit`/`offset`) e `/cart` (`CartOut`:
    `items`/`total`). Nem o legacy nem a lista de asserções portada acima
    afirmam `isinstance(body, list)` explicitamente — só usam
    comprehensions que passariam despercebidas se a rota devolvesse um
    envelope com uma chave `items`/`data` por engano."""

    async def test_get_returns_bare_array_not_envelope(self, client: AsyncClient) -> None:
        await client.post("/payment-methods", json=pix(), headers=headers_for("student"))
        r = await client.get("/payment-methods", headers=headers_for("student"))
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body, list)
        assert body[0]["type"] == "pix"


class TestOrdering:
    """Acréscimo da B9 — item 4: `is_default DESC, created_at ASC`. Nenhum
    teste do legacy prova a ordenação com 3+ métodos em que o default NÃO é
    o criado mais recentemente (os testes portados acima só checam
    `is_default` isolado, nunca a posição na lista)."""

    async def test_default_comes_first_even_when_not_most_recent(self, client: AsyncClient) -> None:
        # Achado da rodada de mutação (task-B9-report.md): uma primeira versão
        # deste teste criava 3 métodos e nunca trocava o default — como o
        # default É o primeiro criado, `created_at ASC` sozinho já dava a
        # ordem certa, e o teste passava mesmo com `.order_by(created_at)`
        # SEM `is_default.desc()` (mutação não pegou — passou por vácuo,
        # constraint 18). Aqui o PATCH torna `third` o default DEPOIS de ser
        # o último criado — só `is_default DESC` explica ele vir primeiro.
        first = (
            await client.post(
                "/payment-methods", json=credit_card(), headers=headers_for("student")
            )
        ).json()  # vira default sozinho (comportamento item 5)
        second = (
            await client.post("/payment-methods", json=pix(), headers=headers_for("student"))
        ).json()
        third = (
            await client.post(
                "/payment-methods", json=pix(pix_key="chave-x"), headers=headers_for("student")
            )
        ).json()

        await client.patch(
            f"/payment-methods/{third['id']}",
            json={"is_default": True},
            headers=headers_for("student"),
        )

        listing = (await client.get("/payment-methods", headers=headers_for("student"))).json()
        assert [m["id"] for m in listing] == [third["id"], first["id"], second["id"]]


class TestCheckConstraintsAtDbLevel:
    """Acréscimo da B9 — item 2: os dois `CheckConstraint`. A API nunca deixa
    esses valores chegarem ao banco (o Pydantic barra antes — ver
    `TestPciSafety`/`TestCreate` acima) — para provar que o CHECK do
    Postgres também existe (defesa em profundidade, não só o schema),
    construímos o objeto ORM diretamente, contornando `PaymentMethodIn`."""

    async def test_type_check_constraint_rejects_invalid_type(
        self, db_session: AsyncSession
    ) -> None:
        db_session.add(PaymentMethod(user_id=uuid.uuid4(), type="crypto"))
        with pytest.raises(IntegrityError):
            await db_session.commit()

    async def test_card_last4_check_constraint_rejects_wrong_length(
        self, db_session: AsyncSession
    ) -> None:
        # "123" (3 chars) cabe na coluna `String(4)` — não dispara truncamento
        # de VARCHAR — mas viola o CHECK `char_length(card_last4) = 4`. Um
        # valor de 5 chars ("12345") dispara `StringDataRightTruncationError`
        # (erro de tamanho de coluna) ANTES de alcançar o CHECK, o que
        # provaria a coluna, não a constraint — medido: a primeira versão
        # deste teste usava "12345" e falhava com
        # `DBAPIError`/`StringDataRightTruncationError`, não `IntegrityError`.
        db_session.add(PaymentMethod(user_id=uuid.uuid4(), type="credit_card", card_last4="123"))
        with pytest.raises(IntegrityError):
            await db_session.commit()


class TestOwnership:
    """Acréscimo da B9 — regra 2 do CLAUDE.md ("nenhuma rota sem controle de
    acesso explícito... nunca consultar dados sem filtro de autorização") e
    o CONTEXTO DO CONTROLADOR do brief, que exige prova nas quatro rotas.
    `headers_for` com dois `sub` diferentes (`STUDENT_A`, `STUDENT_B`)."""

    async def test_get_only_sees_own_methods(self, client: AsyncClient) -> None:
        await client.post(
            "/payment-methods", json=pix(), headers=headers_for("student", sub=STUDENT_A)
        )
        r = await client.get("/payment-methods", headers=headers_for("student", sub=STUDENT_B))
        assert r.status_code == 200, r.text
        assert r.json() == []

    async def test_created_method_belongs_only_to_creator(self, client: AsyncClient) -> None:
        created = (
            await client.post(
                "/payment-methods", json=pix(), headers=headers_for("student", sub=STUDENT_A)
            )
        ).json()
        listing_b = (
            await client.get("/payment-methods", headers=headers_for("student", sub=STUDENT_B))
        ).json()
        assert created["id"] not in [m["id"] for m in listing_b]

    async def test_patch_on_others_method_returns_404(self, client: AsyncClient) -> None:
        method = (
            await client.post(
                "/payment-methods",
                json=credit_card(),
                headers=headers_for("student", sub=STUDENT_A),
            )
        ).json()
        r = await client.patch(
            f"/payment-methods/{method['id']}",
            json={"is_default": True},
            headers=headers_for("student", sub=STUDENT_B),
        )
        assert r.status_code == 404

    async def test_delete_on_others_method_returns_404_and_keeps_it(
        self, client: AsyncClient
    ) -> None:
        method = (
            await client.post(
                "/payment-methods",
                json=credit_card(),
                headers=headers_for("student", sub=STUDENT_A),
            )
        ).json()
        r = await client.delete(
            f"/payment-methods/{method['id']}", headers=headers_for("student", sub=STUDENT_B)
        )
        assert r.status_code == 404

        listing_a = (
            await client.get("/payment-methods", headers=headers_for("student", sub=STUDENT_A))
        ).json()
        assert len(listing_a) == 1
