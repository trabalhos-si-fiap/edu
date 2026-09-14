from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    database_url_test: str = "postgresql+asyncpg://edu:edu@localhost:5433/learning_test"
    rabbitmq_url: str
    exchange_name: str = "edu.events"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    # Ligado só na imagem Docker (ENV no Dockerfile), que já traz o modelo.
    # Falso por padrão para a suíte e o host não carregarem centenas de MB ao
    # subir o app. Ver app/services/embeddings.py::precarregar_modelo.
    precarregar_embeddings: bool = False
    # Usado para gerar a mensagem personalizada do tutor (LLM) ao final do
    # diagnóstico. Se vazio, o serviço cai automaticamente no fallback por
    # template (ver services/tutor_llm.py) — nunca quebra por falta de key.
    groq_api_key: str = ""


settings = Settings()
