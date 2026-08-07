from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    database_url_test: str = "postgresql+asyncpg://edu:edu@localhost:5433/commerce_test"
    rabbitmq_url: str
    exchange_name: str = "edu.events"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    google_maps_api_key: str = ""

    # Redis — memoização da URL presignada (ver app/services/media.py, criado
    # na B2). O serviço não tinha nenhuma dependência de runtime além de
    # Postgres e RabbitMQ; esta é a primeira das duas que a fase 2 acrescenta.
    redis_url: str = "redis://:edu@redis:6379/0"
    # Banco 14, não 15: o legacy usa o 15 (`REDIS_URL_TEST` em
    # `legacy/app/core/config.py:22`) e as duas suítes fazem `flushdb` — rodar
    # as duas ao mesmo tempo no mesmo banco derruba uma delas de forma
    # intermitente. Por decisão de 2026-08-07 a suíte deste serviço usa
    # `fakeredis`, não este Redis real — o campo fica declarado sem
    # consumidor na suíte por ora.
    redis_url_test: str = "redis://:edu@redis:6379/14"

    # Armazenamento de objeto (MinIO em dev, R2 em prod). Os defaults batem
    # com `legacy/app/core/config.py` de propósito: o mesmo bucket serve os
    # dois enquanto o legacy estiver de pé, e uma chave gravada por um tem
    # que ser presignável pelo outro.
    #
    # `r2_public_endpoint_url` é o host contra o qual a URL é ASSINADA — tem
    # que ser alcançável pelo aparelho, não o hostname interno do docker.
    r2_endpoint_url: str = "http://minio:9000"
    r2_public_endpoint_url: str | None = None
    r2_access_key_id: str = "edu"
    r2_secret_access_key: str = "edu-secret"  # noqa: S105 — credencial de dev do MinIO
    r2_region: str = "auto"
    r2_bucket: str = "edu-media"

    # `media_presign_cache_ttl_seconds` TEM que ser menor que
    # `media_presign_ttl_seconds`: o cache guarda a URL assinada, então um
    # cache mais longo que a assinatura devolveria URL expirada.
    media_presign_ttl_seconds: int = 86400
    media_presign_cache_ttl_seconds: int = 82800
    media_max_upload_bytes: int = 5 * 1024 * 1024

    # Chamada serviço-a-serviço para resolver dados que o JWT não carrega:
    # `GET /auth/me` (nome do autor da review) e, a partir do bloco C,
    # `GET /auth/addresses/{id}` (snapshot de entrega no checkout).
    auth_service_url: str = "http://auth-users-service:8000"


settings = Settings()
