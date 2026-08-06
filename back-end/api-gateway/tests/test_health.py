async def test_health_returns_ok(client):
    """`/health` é o que o compose usa como healthcheck. Ele não pode
    depender de nenhum router — se um import de router quebrar, este teste
    tem que continuar sendo a coisa que responde."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
