from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "payments-service"
    api_prefix: str = "/api/v1"
    api_key: str = "change-me-in-env"

    database_url: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/payments"
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"

    outbox_poll_interval_seconds: float = 1.0
    outbox_max_attempts: int = 10


settings = Settings()
