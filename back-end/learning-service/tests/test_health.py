async def test_openapi_schema_is_served(client):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"]


async def test_every_route_is_registered_under_a_known_prefix(client):
    paths = (await client.get("/openapi.json")).json()["paths"]
    known = (
        "/subjects",
        "/topics",
        "/subtopics",
        "/diagnostic",
        "/recommendations",
        "/reviews",
        "/health",
    )
    unknown = [p for p in paths if not p.startswith(known)]
    assert unknown == []


async def test_no_portuguese_path_segment_remains(client):
    """Trava a tradução das rotas públicas: nenhum path pode voltar a ter um
    segmento em português (`/materias`, `/temas`, `/subtemas`,
    `/diagnostico`, `/recomendacoes`/`/relacionados`, `/revisoes`)."""
    paths = (await client.get("/openapi.json")).json()["paths"]
    portuguese_fragments = (
        "materias",
        "temas",
        "subtemas",
        "diagnostico",
        "recomendacoes",
        "relacionados",
        "revisoes",
        "responder",
        "questoes",
        "contexto",
        "questionario",
        "hoje",
    )
    offenders = [p for p in paths if any(fragment in p for fragment in portuguese_fragments)]
    assert offenders == []
