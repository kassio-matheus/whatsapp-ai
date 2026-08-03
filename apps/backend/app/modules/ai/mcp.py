from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import fastmcp
from fastapi import FastAPI
from fastmcp import FastMCP
from fastmcp.client.transports.memory import FastMCPTransport
from mcp import ClientSession

from app.core.config import settings

_backend_app: Any = None

fastmcp.settings.log_enabled = False
_logger = logging.getLogger("fastmcp")
_logger.handlers.clear()
_logger.propagate = False
_logger.setLevel(logging.CRITICAL)

_MCP_TOOL_METHODS = {"get", "post", "put", "patch", "delete"}


def init_mcp(app: FastAPI) -> None:
    """Store the FastAPI app used to build the backend MCP server."""
    global _backend_app
    _backend_app = app


def _slugify(text: str) -> str:
    """Mirror fastmcp's OpenAPI tool-name slug so listings match real names."""
    if not text:
        return ""
    slug = re.sub(r"[\s\-\.]+", "_", text)
    slug = re.sub(r"[^a-zA-Z0-9_]", "", slug)
    slug = re.sub(r"_+", "_", slug)
    return slug.strip("_")


def _friendly_name(operation_id: str) -> str:
    """Turn a FastAPI operationId into a short, stable MCP tool name."""
    return _slugify(operation_id.split("_api_")[0])


def _mcp_names_map() -> dict[str, str]:
    """Map every FastAPI operationId to a friendly MCP tool name."""
    if _backend_app is None:
        return {}
    names: dict[str, str] = {}
    for operations in _backend_app.openapi().get("paths", {}).values():
        for method, operation in operations.items():
            if method not in _MCP_TOOL_METHODS:
                continue
            operation_id = operation.get("operationId")
            if operation_id:
                names[operation_id] = _friendly_name(operation_id)
    return names


def _route_requires_auth(path: str) -> bool:
    """Best-effort heuristic describing which routes need a bearer token."""
    api_prefix = settings.API_V1_PREFIX
    if path.startswith(f"{api_prefix}/auth"):
        return False
    return not ("/webhooks/" in path or "/health" in path)


def list_mcp_tools() -> list[dict[str, Any]]:
    """Describe every MCP tool the backend exposes.

    Names are computed with the same rules fastmcp applies when it builds the
    server, so the identifiers returned here can be used to configure tool
    scoping for WhatsApp contacts.
    """
    if _backend_app is None:
        return []
    spec = _backend_app.openapi()
    names_map = _mcp_names_map()
    used: dict[str, int] = {}
    tools: list[dict[str, Any]] = []
    for path, operations in spec.get("paths", {}).items():
        for method, operation in operations.items():
            if method not in _MCP_TOOL_METHODS:
                continue
            operation_id = operation.get("operationId")
            base_name = names_map.get(operation_id) or _slugify(
                operation_id or f"{method}_{path}"
            )
            used[base_name] = used.get(base_name, 0) + 1
            name = base_name if used[base_name] == 1 else f"{base_name}_{used[base_name]}"
            summary = operation.get("summary")
            tools.append(
                {
                    "name": name,
                    "method": method.upper(),
                    "path": path,
                    "summary": summary,
                    "description": operation.get("description") or summary or "",
                    "requires_auth": _route_requires_auth(path),
                }
            )
    return tools


@asynccontextmanager
async def mcp_session(
    auth_token: str | None = None,
) -> AsyncIterator[ClientSession]:
    """Connect an in-memory MCP client session exposing every backend route.

    The session tools are built from the FastAPI OpenAPI schema, so the model
    has full knowledge of the routes and can call them acting as the user who
    owns ``auth_token``. Callers that only want a subset of the routes (for
    example a WhatsApp contact with restricted MCP access) must filter the
    tool list themselves before invoking the model.
    """
    if _backend_app is None:
        raise RuntimeError(
            "Backend MCP server not initialized. Call init_mcp(app) at startup."
        )

    headers = {"X-AI-Request": "true"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    host = next(
        (h for h in settings.ALLOWED_HOSTS if h and not h.startswith("*")),
        "localhost",
    )

    server = FastMCP.from_fastapi(
        app=_backend_app,
        name="A.I Backend",
        mcp_names=_mcp_names_map(),
        httpx_client_kwargs={
            "base_url": f"http://{host}",
            "timeout": 60,
            "headers": headers,
        },
    )

    transport = FastMCPTransport(mcp=server)
    async with transport.connect_session() as session:
        await session.initialize()
        yield session
