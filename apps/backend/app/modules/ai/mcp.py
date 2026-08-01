from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import fastmcp
from fastapi import FastAPI
from fastmcp import FastMCP
from fastmcp.client.transports.memory import FastMCPTransport
from mcp import ClientSession

_backend_app: Any = None

fastmcp.settings.log_enabled = False
_logger = logging.getLogger("fastmcp")
_logger.handlers.clear()
_logger.propagate = False
_logger.setLevel(logging.CRITICAL)


def init_mcp(app: FastAPI) -> None:
    """Store the FastAPI app used to build the backend MCP server."""
    global _backend_app
    _backend_app = app


@asynccontextmanager
async def mcp_session(
    auth_token: str | None = None,
) -> AsyncIterator[ClientSession]:
    """Connect an in-memory MCP client session exposing every backend route.

    The session tools are built from the FastAPI OpenAPI schema, so the model
    has full knowledge of the routes and can call them acting as the user who
    owns ``auth_token``.
    """
    if _backend_app is None:
        raise RuntimeError(
            "Backend MCP server not initialized. Call init_mcp(app) at startup."
        )

    headers = {"X-AI-Request": "true"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    server = FastMCP.from_fastapi(
        app=_backend_app,
        name="A.I Backend",
        httpx_client_kwargs={
            "base_url": "http://localhost",
            "timeout": 60,
            "headers": headers,
        },
    )

    transport = FastMCPTransport(mcp=server)
    async with transport.connect_session() as session:
        await session.initialize()
        yield session
