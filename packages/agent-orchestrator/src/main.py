"""Entrypoint for the Agent Orchestrator service."""

from __future__ import annotations

import uvicorn

from src.api.app import create_app
from src.config import settings

app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
