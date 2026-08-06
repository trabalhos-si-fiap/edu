from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    database_url_test: str = "postgresql+asyncpg://edu:edu@localhost:5433/auth_test"
    rabbitmq_url: str
    exchange_name: str = "edu.events"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # Sem `cors_origins` aqui de propósito: CORS é do gateway
    # (`api-gateway/app/main.py`), o serviço browser-facing — o app fala com
    # o gateway, não com este serviço direto. Este serviço não usa cookie:
    # auth é só Bearer token via Authorization header
    # (`edu_common.deps.build_auth_deps`), então não há credencial ambiente
    # que um CSRF cross-origin pudesse anexar sozinho. O campo estava
    # declarado e nenhum middleware o lia (ver
    # tests/test_main.py::test_no_cors_middleware_mounted).


settings = Settings()
