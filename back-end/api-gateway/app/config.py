from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

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

    # Teto do corpo que o gateway aceita acumular em memória antes de
    # repassar. O proxy monta o corpo ANTES de qualquer autenticação, então
    # sem teto um POST anônimo de megabytes já custa a memória do gateway —
    # comprovado na fase 1 com 9,6 MB. `app/main.py` compara o acumulado a
    # cada pedaço de `request.stream()` e aborta no primeiro que passa daqui,
    # então o corpo nunca é lido inteiro. Este número NÃO é o pico de
    # memória: o pico é ele mais o pedaço que estourou o teto — no teste do
    # cap, 2 200 000 bytes contra um teto de 2 097 152. Ver a ressalva sobre
    # pedaço isolado em `app/main.py`. 2 MiB cobre com
    # folga o maior corpo que o app envia hoje (JSON de pedido/endereço);
    # upload de imagem é fase 3 e vai precisar de um caminho próprio, não
    # deste.
    max_request_body_bytes: int = 2 * 1024 * 1024

    # Origens liberadas para CORS (lista JSON via env CORS_ORIGINS). Sem
    # curinga — allow_credentials=True com "*" é rejeitado pelo browser e
    # vazaria a API para qualquer site.
    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
