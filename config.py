from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/payments"

    # Bank API (external)
    bank_api_base_url: str = "https://bank.api"
    bank_api_timeout_seconds: float = 10.0
