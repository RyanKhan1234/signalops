"""Configuration management for SignalOps MCP Wrapper.

All configuration is sourced from environment variables. No secrets are
ever hardcoded. Call ``get_config()`` to obtain a validated ``Config``
instance; this function is cached so the environment is only read once.
"""

from __future__ import annotations

import functools
import os

from pydantic import BaseModel, Field, field_validator


class Config(BaseModel):
    """Typed, validated application configuration."""

    # SerpApi
    serpapi_api_key: str = Field(description="SerpApi API key (required)")
    serpapi_base_url: str = Field(
        default="https://serpapi.com/search",
        description="SerpApi endpoint URL",
    )

    # Cache
    cache_ttl_seconds: int = Field(
        default=900,
        ge=0,
        description="TTL for news search cache entries (seconds)",
    )
    cache_ttl_metadata_seconds: int = Field(
        default=3600,
        ge=0,
        description="TTL for article metadata cache entries (seconds)",
    )

    # Rate limiting
    rate_limit_per_minute: int = Field(
        default=30,
        ge=1,
        description="Maximum SerpApi requests per minute",
    )
    rate_limit_per_day: int = Field(
        default=1000,
        ge=1,
        description="Maximum SerpApi requests per day",
    )

    # MCP transport
    mcp_transport: str = Field(
        default="stdio",
        description="MCP transport mode: 'stdio' or 'sse'",
    )
    mcp_sse_port: int = Field(
        default=8001,
        ge=1,
        le=65535,
        description="Port for SSE transport",
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    @field_validator("mcp_transport")
    @classmethod
    def validate_transport(cls, v: str) -> str:
        allowed = {"stdio", "sse"}
        if v.lower() not in allowed:
            raise ValueError(f"mcp_transport must be one of {allowed}; got {v!r}")
        return v.lower()

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}; got {v!r}")
        return upper


@functools.lru_cache(maxsize=1)
def get_config() -> Config:
    """Return the singleton ``Config`` instance (reads environment once)."""
    return Config(
        serpapi_api_key=os.environ.get("SERPAPI_API_KEY", ""),
        serpapi_base_url=os.environ.get(
            "SERPAPI_BASE_URL", "https://serpapi.com/search"
        ),
        cache_ttl_seconds=int(os.environ.get("CACHE_TTL_SECONDS", "900")),
        cache_ttl_metadata_seconds=int(
            os.environ.get("CACHE_TTL_METADATA_SECONDS", "3600")
        ),
        rate_limit_per_minute=int(os.environ.get("RATE_LIMIT_PER_MINUTE", "30")),
        rate_limit_per_day=int(os.environ.get("RATE_LIMIT_PER_DAY", "1000")),
        mcp_transport=os.environ.get("MCP_TRANSPORT", "stdio"),
        mcp_sse_port=int(os.environ.get("MCP_SSE_PORT", "8001")),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
