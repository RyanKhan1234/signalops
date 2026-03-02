"""Configuration management for the Agent Orchestrator service."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Anthropic / LLM
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-6"

    # Service URLs
    mcp_wrapper_url: str = "http://localhost:8001"
    traceability_store_url: str = "http://localhost:8002"

    # FastAPI server
    host: str = "0.0.0.0"
    port: int = 8000

    # Pipeline config
    guardrails_max_retries: int = 2

    # Logging
    log_level: str = "INFO"

    # Correlation ID header
    correlation_id_header: str = "X-Request-ID"


settings = Settings()
