from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    database_url_test: str = "postgresql+asyncpg://edu:edu@localhost:5433/notification_test"
    rabbitmq_url: str
    exchange_name: str = "edu.events"
    jwt_secret: str
    jwt_algorithm: str = "HS256"

    # E-mail. O backend volta a existir nesta spec (spec C, D1): a spec A
    # apagou o remetente junto com o monolito.
    #
    # `console` é o default e não fala com a rede — é o que roda em
    # desenvolvimento e na suíte. `resend` exige `RESEND_API_KEY`; o domínio
    # `svemlab.com` está verificado no Resend (MX `send`, DKIM
    # `resend._domainkey`, SPF `send`), e `no-reply@` não precisa de caixa
    # postal real por ser só de saída.
    email_backend: str = "console"
    resend_api_key: str = ""
    email_from: str = "no-reply@svemlab.com"


settings = Settings()
