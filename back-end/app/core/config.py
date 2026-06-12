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

    # Delivery tracking / route prediction. While the real routing provider
    # (e.g. Google Maps) is not integrated, the ETA is estimated locally from
    # the great-circle distance corrected by an urban-route factor (to account
    # for streets, turns and detours) and a configurable average speed.
    TRACKING_AVERAGE_SPEED_KMH: float = 30.0
    TRACKING_URBAN_ROUTE_FACTOR: float = 1.4


settings = Settings()
