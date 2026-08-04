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
    # Usado para gerar a mensagem personalizada do tutor (LLM) ao final do
    # diagnóstico. Se vazio, o serviço cai automaticamente no fallback por
    # template (ver services/tutor_llm.py) — nunca quebra por falta de key.
    groq_api_key: str = ""


settings = Settings()
