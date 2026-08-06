from app.main import app


def test_no_cors_middleware_mounted():
    """Este serviço não monta `CORSMiddleware` — CORS é responsabilidade só
    do gateway (`api-gateway/app/main.py`), que é quem o browser alcança.
    Todas as rotas de auth usam `Authorization: Bearer` (`HTTPBearer` via
    `edu_common.deps.build_auth_deps`), nunca cookie — não há credencial
    ambiente que um form cross-origin pudesse anexar sozinho, então a
    ausência de CORS aqui não deixa uma rota estatal exposta a CSRF."""
    cors = [m for m in app.user_middleware if "CORSMiddleware" in str(m)]
    assert not cors
