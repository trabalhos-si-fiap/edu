async def test_openapi_schema_is_served(client):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"]


async def test_every_route_is_registered_under_a_known_prefix(client):
    paths = (await client.get("/openapi.json")).json()["paths"]
    known = ("/auth", "/users", "/health")
    unknown = [p for p in paths if not p.startswith(known)]
    assert unknown == []
