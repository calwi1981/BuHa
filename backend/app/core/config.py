from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BUHA"
    app_env: str = "production"
    app_domain: str = "localhost"
    app_url: str = "http://localhost:8000"

    database_url: str
    secret_key: str

    initial_admin_username: str = "admin"
    initial_admin_email: str = ""
    initial_admin_password: str = ""

    session_cookie_secure: bool = True

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_starttls: bool = True

    default_currency: str = "EUR"
    default_language: str = "de"
    default_vat_rate: int = 19

    tz: str = "Europe/Berlin"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
