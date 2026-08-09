"""Teste de forma do payload de rota (schema/serialização, sem banco).

Porte de `legacy/tests/test_tracking_schemas.py` (task C9, arquivo
inteiro). Sem adaptação de conteúdo além do import: `RouteOut`/`RoutePoint`
moram em `app.schemas.rastreio`, não em `app.modules.tracking.schemas`. A
suíte deste serviço já paga o custo de um Postgres real via a fixture
autouse `_clean_tables` do `conftest.py` (regra do CLAUDE.md: testes de
integração com banco real, não mocks) — diferente do legacy, não é preciso
sobrescrever nenhuma fixture aqui para este teste rodar sem rede/DB própria.
"""

from app.schemas.rastreio import RouteOut, RoutePoint


def test_route_out_serializes_expected_keys_and_rounds_distance() -> None:
    payload = RouteOut(
        origin=RoutePoint(label="Centro de Distribuição", latitude=-23.3558, longitude=-46.8769),
        destination=RoutePoint(
            label="Endereço de entrega", latitude=-23.561414, longitude=-46.655881
        ),
        polyline="abc123",
        distance_text="32 km",
        distance_km=32.123456,
        duration_text="48 min",
        duration_minutes=48,
    )

    dumped = payload.model_dump()
    assert set(dumped) == {
        "origin",
        "destination",
        "polyline",
        "distance_text",
        "distance_km",
        "duration_text",
        "duration_minutes",
    }
    assert set(dumped["origin"]) == {"label", "latitude", "longitude"}
    assert dumped["distance_km"] == 32.123  # arredondado para 3 casas
