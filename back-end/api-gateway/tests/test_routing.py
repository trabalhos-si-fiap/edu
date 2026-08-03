import pytest

from app.routing import SERVICE_MAP, resolve_destination


@pytest.mark.parametrize(
    ("path", "expected_service"),
    [
        ("auth/login", "auth"),
        ("users/me", "auth"),
        ("addresses", "auth"),
        ("subjects", "learning"),
        ("topics/1/subtopics", "learning"),
        ("diagnostic/answer", "learning"),
        ("recommendations", "learning"),
        ("reviews/today", "learning"),
        ("products", "commerce"),
        ("orders/1/tracking", "commerce"),
        ("cart/items", "commerce"),
        ("payment-methods", "commerce"),
        ("picking/queue", "commerce"),
        ("delivery/1/collect", "commerce"),
        ("occurrences", "commerce"),
        ("notifications/devices", "notification"),
        ("analytics/summary", "analytics"),
        ("chat/explain-question", "chatbot"),
        ("support", "chatbot"),
    ],
)
def test_first_segment_resolves_to_expected_service(path: str, expected_service: str):
    assert SERVICE_MAP[path.split("/", 1)[0]] == expected_service


def test_resolve_destination_keeps_full_path():
    destination = resolve_destination("orders/42/tracking")
    assert destination is not None
    base_url, final_path = destination
    assert final_path == "/orders/42/tracking"
    assert base_url.startswith("http")


def test_resolve_destination_returns_none_for_unmapped_path():
    assert resolve_destination("rota-inexistente") is None


def test_resolve_destination_returns_none_for_empty_path():
    assert resolve_destination("") is None


def test_no_portuguese_paths_remain_in_the_public_contract():
    portuguese = {
        "produtos",
        "pedidos",
        "separacao",
        "entrega",
        "ocorrencias",
        "materias",
        "temas",
        "subtemas",
        "diagnostico",
        "recomendacoes",
        "revisoes",
    }
    assert portuguese.isdisjoint(SERVICE_MAP.keys())
