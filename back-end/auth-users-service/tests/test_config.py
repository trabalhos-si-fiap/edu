from app.config import settings


def test_settings_has_no_cors_origins():
    """`cors_origins` foi removido de propósito: CORS é responsabilidade do
    gateway (`api-gateway/app/main.py`), que é quem o browser alcança. O
    campo estava declarado aqui e nenhum middleware deste serviço o lia
    (ver `tests/test_main.py::test_no_cors_middleware_mounted`). Este teste
    falha se o campo voltar."""
    assert not hasattr(settings, "cors_origins")
