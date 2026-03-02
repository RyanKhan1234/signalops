"""Traceability Store service entrypoint.

Run with:
    uvicorn src.main:app --host 0.0.0.0 --port 8002
"""

import logging

import uvicorn

from src.api.app import create_app
from src.config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
)

app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=settings.api_port,
        log_level=settings.log_level.lower(),
    )
