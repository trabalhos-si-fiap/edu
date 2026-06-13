from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Edu - Estuda App"
    ENV: str = "development"
    DEBUG: bool = False

    # All module routers are mounted under this prefix (faithful to the
    # original `/api/` client contract). `/health` stays at the root.
    API_PREFIX: str = "/api"

    DATABASE_URL: str = "postgresql+asyncpg://edu:edu@postgres:5432/edu"
    DATABASE_URL_TEST: str = "postgresql+asyncpg://edu:edu@postgres:5432/edu_test"
    REDIS_URL: str = "redis://:edu@redis:6379/0"
    REDIS_URL_TEST: str = "redis://:edu@redis:6379/15"

    CELERY_BROKER_URL: str = "amqp://edu:edu@rabbitmq:5672//"
    CELERY_RESULT_BACKEND: str = "redis://:edu@redis:6379/1"

    SECRET_KEY: str = "change-me-in-production"  # noqa: S105
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    BCRYPT_ROUNDS: int = 12

    LOGIN_RATE_LIMIT_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 900

    # Path to the Firebase service account JSON used by the Admin SDK to send
    # push notifications. Mounted into the api/worker containers as a secret;
    # never commit the file itself (see project .gitignore).
    FIREBASE_CREDENTIALS_PATH: str | None = None
    FCM_SEND_TIME_LIMIT: int = 30
    FCM_SEND_SOFT_TIME_LIMIT: int = 25

    # Order delivery status pipeline. Real logistics events are simulated for
    # this demo: after checkout, the order advances through its lifecycle
    # automatically, waiting a random delay (seconds) between each transition.
    ORDER_STATUS_MIN_DELAY_SECONDS: int = 10
    ORDER_STATUS_MAX_DELAY_SECONDS: int = 30
    ORDER_STATUS_TASK_TIME_LIMIT: int = 30
    ORDER_STATUS_TASK_SOFT_TIME_LIMIT: int = 25

    # Delivery tracking / route prediction. While the real routing provider
    # (e.g. Google Maps) is not integrated, the ETA is estimated locally from
    # the great-circle distance corrected by an urban-route factor (to account
    # for streets, turns and detours) and a configurable average speed.
    TRACKING_AVERAGE_SPEED_KMH: float = 30.0
    TRACKING_URBAN_ROUTE_FACTOR: float = 1.4

    # Google Maps Platform key used server-side to call the Directions API for
    # the order-route map. Lives in back-end/.env; never sent to the client.
    # (Spelling matches the key the operator created in .env.)
    GOOGLE_MAPS_API_PLATAFORM: str | None = None
    # Time-to-live for a cached order route. Origin and destination are fixed
    # per order, so the route is stable — cache it to avoid repeat Directions
    # calls (and cost).
    TRACKING_ROUTE_CACHE_TTL_SECONDS: int = 21600  # 6 hours

    # Object storage for product images. Cloudflare R2 in prod, MinIO in dev —
    # both speak the S3 API, so only the endpoint/credentials change. The bucket
    # is private; clients read via short-lived presigned GET URLs. Defaults point
    # at the dev MinIO; prod must set these env vars to the R2 values.
    R2_ENDPOINT_URL: str = "http://minio:9000"
    R2_PUBLIC_ENDPOINT_URL: str | None = None  # URL host reachable by the app/client
    R2_ACCESS_KEY_ID: str = "edu"
    R2_SECRET_ACCESS_KEY: str = "edu-secret"  # noqa: S105
    R2_REGION: str = "auto"
    R2_BUCKET: str = "edu-media"
    # Presigned URL lifetime, and how long we memoize a generated URL in Redis
    # (kept under the lifetime so a cached URL never hands out an almost-expired link).
    MEDIA_PRESIGN_TTL_SECONDS: int = 86400
    MEDIA_PRESIGN_CACHE_TTL_SECONDS: int = 82800
    # Max accepted upload size for a product image.
    MEDIA_MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024


settings = Settings()
