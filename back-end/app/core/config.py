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


settings = Settings()
