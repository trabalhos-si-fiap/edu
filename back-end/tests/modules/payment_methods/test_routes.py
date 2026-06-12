import uuid

from httpx import AsyncClient

from tests.modules.payment_methods.conftest import credit_card, pix


class TestAuthRequired:
    async def test_list_requires_auth(self, client: AsyncClient) -> None:
        r = await client.get("/api/payment-methods")
        assert r.status_code == 401


class TestPciSafety:
    async def test_full_card_number_is_rejected(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        # A client must never send the full PAN; extra fields are forbidden.
        payload = credit_card(card_number="4111111111111111")
        r = await client.post("/api/payment-methods", json=payload, headers=auth_headers)
        assert r.status_code == 422

    async def test_cvv_is_rejected(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        payload = credit_card(cvv="123")
        r = await client.post("/api/payment-methods", json=payload, headers=auth_headers)
        assert r.status_code == 422

    async def test_card_last4_must_be_four_digits(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.post(
            "/api/payment-methods",
            json=credit_card(card_last4="4111111111111111"),
            headers=auth_headers,
        )
        assert r.status_code == 422

    async def test_stored_method_never_exposes_secret_fields(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.post(
            "/api/payment-methods", json=credit_card(), headers=auth_headers
        )
        body = r.json()
        for forbidden in ("card_number", "pan", "cvv", "cardholder_tax_id"):
            assert forbidden not in body
        assert body["card_last4"] == "1234"


class TestCreate:
    async def test_first_method_is_default(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.post(
            "/api/payment-methods", json=credit_card(), headers=auth_headers
        )
        assert r.status_code == 201, r.text
        assert r.json()["is_default"] is True

    async def test_credit_card_missing_fields_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.post(
            "/api/payment-methods",
            json={"type": "credit_card", "card_last4": "1234"},
            headers=auth_headers,
        )
        assert r.status_code == 422

    async def test_pix_requires_key(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.post(
            "/api/payment-methods", json={"type": "pix"}, headers=auth_headers
        )
        assert r.status_code == 422

    async def test_pix_happy_path(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.post("/api/payment-methods", json=pix(), headers=auth_headers)
        assert r.status_code == 201, r.text
        assert r.json()["pix_key"] == "maria@example.com"

    async def test_second_default_unsets_first(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        first = (
            await client.post("/api/payment-methods", json=credit_card(), headers=auth_headers)
        ).json()
        await client.post(
            "/api/payment-methods", json=pix(is_default=True), headers=auth_headers
        )
        listing = (await client.get("/api/payment-methods", headers=auth_headers)).json()
        defaults = [m for m in listing if m["is_default"]]
        assert len(defaults) == 1
        assert defaults[0]["type"] == "pix"
        first_now = next(m for m in listing if m["id"] == first["id"])
        assert first_now["is_default"] is False


class TestSetDefaultAndDelete:
    async def test_patch_sets_default(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        await client.post("/api/payment-methods", json=credit_card(), headers=auth_headers)
        second = (
            await client.post("/api/payment-methods", json=pix(), headers=auth_headers)
        ).json()

        r = await client.patch(
            f"/api/payment-methods/{second['id']}",
            json={"is_default": True},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["is_default"] is True

    async def test_delete_promotes_remaining_to_default(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        first = (
            await client.post("/api/payment-methods", json=credit_card(), headers=auth_headers)
        ).json()  # default
        second = (
            await client.post("/api/payment-methods", json=pix(), headers=auth_headers)
        ).json()

        r = await client.delete(
            f"/api/payment-methods/{first['id']}", headers=auth_headers
        )
        assert r.status_code == 204

        listing = (await client.get("/api/payment-methods", headers=auth_headers)).json()
        assert len(listing) == 1
        assert listing[0]["id"] == second["id"]
        assert listing[0]["is_default"] is True

    async def test_delete_unknown_returns_404(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.delete(
            f"/api/payment-methods/{uuid.uuid4()}", headers=auth_headers
        )
        assert r.status_code == 404
