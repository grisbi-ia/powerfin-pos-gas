"""Application configuration loaded from environment variables."""

from datetime import timedelta, timezone

from pydantic_settings import BaseSettings

# Ecuador timezone (UTC-5). Used consistently across the whole backend.
ECUADOR_TZ = timezone(timedelta(hours=-5))


class Settings(BaseSettings):
    # Database
    database_host: str = "localhost"
    database_port: int = 5433
    database_name: str = "powerfin_gas"
    database_user: str = "postgres"
    database_password: str = ""

    # Auth
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # App
    app_name: str = "Powerfin POS Backend"
    app_version: str = "1.0.0"
    debug: bool = True
    cors_origins: str = "*"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql+psycopg2://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
