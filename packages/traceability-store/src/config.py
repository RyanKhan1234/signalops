"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings for the Traceability Store service."""

    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/signalops"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Server
    api_port: int = 8002
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
