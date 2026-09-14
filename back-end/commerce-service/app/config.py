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
    # Ligado só na imagem Docker (ENV no Dockerfile), que já traz o modelo.
    # Falso por padrão para a suíte e o host não carregarem centenas de MB ao
    # subir o app. Ver app/services/embeddings.py::precarregar_modelo.
    precarregar_embeddings: bool = False
    google_maps_api_key: str = ""

    # Rastreio. Os três valores batem com `legacy/app/core/config.py:70,71,80`
    # (`grep -n "TRACKING_" back-end/legacy/app/core/config.py` ->
    # `TRACKING_AVERAGE_SPEED_KMH: float = 30.0`,
    # `TRACKING_URBAN_ROUTE_FACTOR: float = 1.4`,
    # `TRACKING_ROUTE_CACHE_TTL_SECONDS: int = 21600`). Nenhum teste da suíte
    # asserta sobre estes três números — medido na rodada de correção 1
    # mutando os três (30.0->77.0, 1.4->3.3, 21600->7) e rodando `uv run
    # pytest -q`: 340 passed, sem nenhuma falha. Mudar qualquer um aqui não
    # quebra nada automaticamente; se quiser divergir do legacy, é seguro
    # fazê-lo, só documente o motivo aqui.
    tracking_average_speed_kmh: float = 30.0
    tracking_urban_route_factor: float = 1.4
    tracking_route_cache_ttl_seconds: int = 21600  # 6 horas

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

    # Confirmação de pagamento SEM verificação nenhuma: ligado, `POST /orders`
    # encadeia CRIADO -> CONFIRMADO -> AGUARDANDO_SEPARACAO logo depois de
    # gravar o pedido, pelo mesmo caminho do clique do admin
    # (`app/routers/admin.py::confirmar_pagamento_do_pedido`). Não há provedor
    # de pagamento por trás — é o roteiro da demonstração, não uma cobrança.
    # Falso por padrão para a suíte manter o sentido de todo teste que cria
    # pedido; o `docker-compose.yml` o liga.
    confirmar_pagamento_automatico: bool = False

    # Rede de segurança da apresentação: avança um pedido parado no mesmo
    # estado há mais que este prazo. AUSENTE (0) É DESLIGADO — o default do
    # código, e o critério de pronto 6 da spec C.
    #
    # O `docker-compose.yml` o liga com 180 (três minutos), por pedido do
    # roteiro gravado: "cada passo avança sozinho depois de 3 minutos". O
    # custo é conhecido — quem alterna entre quatro perfis num aparelho só
    # pode ver o pedido correr na frente se demorar mais que isso num passo,
    # e o que a rede de segurança faz no lugar de uma pessoa (sem separador,
    # sem entregador no pedido) está em `docs/back-end/order-flow.md` §4.
    avanco_automatico_segundos: int = 0
    # De quanto em quanto tempo o simulador grava uma posição nova. Dez
    # segundos casa com o polling do app (`OrderProvider`, 8s).
    simulador_posicao_segundos: int = 10


settings = Settings()
