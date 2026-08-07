async def test_health_returns_ok(client):
    """Trava o contrato de `GET /health`: 200 com exatamente
    `{"status": "ok"}`. Checar só o status deixaria passar uma resposta
    com outro corpo — esta task existe porque a frota tinha testes de
    "health" que nunca chegavam a bater em `/health`."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
