from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # URLs internas (rede Docker) — sempre porta 8000, que é a porta que
    # cada serviço expõe DENTRO do container (o mapeamento 8001:8000 etc.
    # no docker-compose.yml só vale para acesso de fora do Docker).
    auth_service_url: str = "http://auth-users-service:8000"
    learning_service_url: str = "http://learning-service:8000"
    commerce_service_url: str = "http://commerce-service:8000"
    notification_service_url: str = "http://notification-service:8000"
    analytics_service_url: str = "http://analytics-service:8000"
    chatbot_service_url: str = "http://chatbot-service:8000"

    request_timeout_seconds: float = 30.0

    class Config:
        env_file = ".env"


settings = Settings()
