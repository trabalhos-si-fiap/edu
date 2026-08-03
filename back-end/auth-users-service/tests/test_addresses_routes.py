REGISTER = {
    "name": "Maria",
    "email": "maria@teste.com",
    "phone": "11999999999",
    "birth_date": "15/06/2005",
    "education_level": "3º ano",
    "password": "Senha@123",
}
OTHER = {
    "name": "Pedro",
    "email": "pedro@teste.com",
    "phone": "11988888888",
    "birth_date": "20/03/1998",
    "education_level": "Vestibulando",
    "password": "Senha@123",
}

ADDRESS = {
    "label": "Casa",
    "zip_code": "01001-000",
    "street": "Praça da Sé",
    "number": "1",
    "complement": "",
    "neighborhood": "Sé",
    "city": "São Paulo",
    "state": "SP",
    "is_favorite": True,
}


async def _register(client, payload) -> dict[str, str]:
    tokens = (await client.post("/auth/register", json=payload)).json()
    return {"Authorization": f"Bearer {tokens['tokens']['access_token']}"}


async def test_create_and_list_own_address(client):
    headers = await _register(client, REGISTER)
    created = await client.post("/auth/addresses", json=ADDRESS, headers=headers)
    assert created.status_code == 201

    listed = await client.get("/auth/addresses", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["street"] == "Praça da Sé"


async def test_addresses_require_authentication(client):
    assert (await client.get("/auth/addresses")).status_code == 403


async def test_user_cannot_see_another_users_addresses(client):
    maria = await _register(client, REGISTER)
    await client.post("/auth/addresses", json=ADDRESS, headers=maria)

    pedro = await _register(client, OTHER)
    assert (await client.get("/auth/addresses", headers=pedro)).json() == []


async def test_user_cannot_patch_another_users_address(client):
    maria = await _register(client, REGISTER)
    address_id = (await client.post("/auth/addresses", json=ADDRESS, headers=maria)).json()["id"]

    pedro = await _register(client, OTHER)
    response = await client.patch(
        f"/auth/addresses/{address_id}", json={"label": "Roubado"}, headers=pedro
    )
    assert response.status_code == 404


async def test_user_cannot_delete_another_users_address(client):
    maria = await _register(client, REGISTER)
    address_id = (await client.post("/auth/addresses", json=ADDRESS, headers=maria)).json()["id"]

    pedro = await _register(client, OTHER)
    assert (await client.delete(f"/auth/addresses/{address_id}", headers=pedro)).status_code == 404


async def test_list_addresses_is_paginated(client):
    headers = await _register(client, REGISTER)
    for i in range(3):
        await client.post("/auth/addresses", json={**ADDRESS, "number": str(i)}, headers=headers)
    response = await client.get("/auth/addresses?limit=2", headers=headers)
    assert len(response.json()) == 2


async def test_patch_with_non_uuid_address_id_returns_4xx_not_500(client):
    """Additional scope (task 7 review finding, not in the brief):
    `address_id` was typed `str` on PATCH/DELETE, binding a raw string
    straight to a UUID column — a non-UUID id reached asyncpg and blew up as
    a 500 instead of a clean 4xx."""
    headers = await _register(client, REGISTER)
    response = await client.patch(
        "/auth/addresses/not-a-uuid", json={"label": "X"}, headers=headers
    )
    assert 400 <= response.status_code < 500


async def test_delete_with_non_uuid_address_id_returns_4xx_not_500(client):
    headers = await _register(client, REGISTER)
    response = await client.delete("/auth/addresses/not-a-uuid", headers=headers)
    assert 400 <= response.status_code < 500
