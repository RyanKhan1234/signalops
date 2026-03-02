"""Entrypoint for the SignalOps MCP Wrapper server.

Reads ``MCP_TRANSPORT`` from the environment (``"stdio"`` or ``"sse"``) and
starts the server on the appropriate transport.

Usage::

    # stdio transport (default — used when called by an MCP client directly)
    python -m src.main

    # SSE transport (for HTTP-based deployment)
    MCP_TRANSPORT=sse MCP_SSE_PORT=8001 python -m src.main
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from src.config import get_config  # noqa: E402 (must be after load_dotenv)
from src.server import server  # noqa: E402


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )


async def _run_stdio() -> None:
    """Run the MCP server on stdio transport."""
    from mcp.server.stdio import stdio_server

    config = get_config()
    _configure_logging(config.log_level)
    logger = logging.getLogger(__name__)
    logger.info("Starting SignalOps MCP Wrapper (stdio transport)")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


async def _dispatch_tool_rest(name: str, arguments: dict) -> dict:
    """Dispatch REST tool call to the appropriate handler."""
    from src.server import (
        _metadata_cache,
        _rate_limiter,
        _search_cache,
        _serpapi_client,
    )
    from src.tools.get_article_metadata import execute_get_article_metadata
    from src.tools.search_company_news import execute_search_company_news
    from src.tools.search_news import execute_search_news

    if name == "search_news":
        return await execute_search_news(
            query=arguments.get("query", ""),
            time_range=arguments.get("time_range", "7d"),
            num_results=arguments.get("num_results", 10),
            client=_serpapi_client,
            cache=_search_cache,
            rate_limiter=_rate_limiter,
        )
    elif name == "search_company_news":
        return await execute_search_company_news(
            company=arguments.get("company", ""),
            time_range=arguments.get("time_range", "7d"),
            topics=arguments.get("topics"),
            client=_serpapi_client,
            cache=_search_cache,
            rate_limiter=_rate_limiter,
        )
    elif name == "get_article_metadata":
        return await execute_get_article_metadata(
            url=arguments.get("url", ""),
            client=_serpapi_client,
            cache=_metadata_cache,
            rate_limiter=_rate_limiter,
        )
    else:
        return {
            "error": {
                "code": "UNKNOWN_TOOL",
                "message": f"Unknown tool: {name!r}",
                "details": {},
                "retry_after_seconds": None,
            }
        }


async def _run_sse() -> None:
    """Run the MCP server on SSE transport."""
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route

    import uvicorn

    config = get_config()
    _configure_logging(config.log_level)
    logger = logging.getLogger(__name__)
    logger.info(
        "Starting SignalOps MCP Wrapper (SSE transport) on port %d",
        config.mcp_sse_port,
    )

    sse = SseServerTransport("/messages/")

    async def handle_sse(request):  # type: ignore[no-untyped-def]
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await server.run(
                streams[0],
                streams[1],
                server.create_initialization_options(),
            )

    async def handle_tool_rest(request: Request) -> JSONResponse:
        name = request.path_params["name"]
        try:
            body = await request.json()
        except Exception:
            body = {}

        result = await _dispatch_tool_rest(name, body)
        return JSONResponse(result)

    starlette_app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Route("/tools/{name}", endpoint=handle_tool_rest, methods=["POST"]),
            Mount("/messages/", app=sse.handle_post_message),
        ]
    )

    uvicorn_config = uvicorn.Config(
        starlette_app,
        host="0.0.0.0",
        port=config.mcp_sse_port,
        log_level=config.log_level.lower(),
    )
    uvicorn_server = uvicorn.Server(uvicorn_config)
    await uvicorn_server.serve()


def main() -> None:
    """Select transport and run the server."""
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    if transport == "sse":
        asyncio.run(_run_sse())
    else:
        asyncio.run(_run_stdio())


if __name__ == "__main__":
    main()
