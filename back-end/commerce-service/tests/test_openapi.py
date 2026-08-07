async def test_openapi_schema_is_served(client):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"]
