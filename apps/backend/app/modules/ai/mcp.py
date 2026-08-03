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
_mcp_server: FastMCP | None = None
_tools_cache: list[Any] | None = None

fastmcp.settings.log_enabled = False

_logger = logging.getLogger("fastmcp")
_logger.handlers.clear()
_logger.propagate = False
_logger.setLevel(logging.CRITICAL)

_MCP_TOOL_METHODS = {"get", "post", "put", "patch", "delete"}


def init_mcp(app: FastAPI) -> None:
    global _backend_app, _mcp_server, _tools_cache

    _backend_app = app

    # invalida cache caso reload da aplicação aconteça
    _mcp_server = None
    _tools_cache = None


def _slugify(text: str) -> str:
    if not text:
        return ""

    slug = re.sub(r"[\s\-\.]+", "_", text)
    slug = re.sub(r"[^a-zA-Z0-9_]", "", slug)
    slug = re.sub(r"_+", "_", slug)

    return slug.strip("_")


def _friendly_name(operation_id: str) -> str:
    return _slugify(operation_id.split("_api_")[0])


def _mcp_names_map() -> dict[str, str]:
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
    api_prefix = settings.API_V1_PREFIX

    if path.startswith(f"{api_prefix}/auth"):
        return False

    return not (
        "/webhooks/" in path
        or "/health" in path
    )


def list_mcp_tools() -> list[dict[str, Any]]:
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

            base_name = (
                names_map.get(operation_id)
                or _slugify(operation_id or f"{method}_{path}")
            )

            used[base_name] = used.get(base_name, 0) + 1

            name = (
                base_name
                if used[base_name] == 1
                else f"{base_name}_{used[base_name]}"
            )

            summary = operation.get("summary")

            tools.append(
                {
                    "name": name,
                    "method": method.upper(),
                    "path": path,
                    "summary": summary,
                    "description": (
                        operation.get("description")
                        or summary
                        or ""
                    ),
                    "requires_auth": _route_requires_auth(path),
                }
            )

    return tools


def find_available_tools(query: str) -> list[dict[str, Any]]:
    global _tools_cache

    if _tools_cache is None:
        _tools_cache = list_mcp_tools()

    query = query.lower().strip()

    if not query:
        return _tools_cache[:20]

    result = []

    for tool in _tools_cache:

        content = " ".join(
            [
                tool["name"],
                tool["path"],
                tool.get("summary") or "",
                tool.get("description") or "",
            ]
        ).lower()

        if query in content:
            result.append(tool)

    return result[:20]


def get_mcp_server() -> FastMCP:
    global _mcp_server

    if _backend_app is None:
        raise RuntimeError(
            "Backend MCP server not initialized."
        )

    if _mcp_server is None:

        _mcp_server = FastMCP.from_fastapi(
            app=_backend_app,
            name="A.I Backend",
            mcp_names=_mcp_names_map(),
        )

    return _mcp_server


async def get_tools(session: ClientSession):
    global _tools_cache

    if _tools_cache is None:
        _tools_cache = list(
            (await session.list_tools()).tools
        )

    return _tools_cache


@asynccontextmanager
async def mcp_session(
    auth_token: str | None = None,
) -> AsyncIterator[ClientSession]:

    server = get_mcp_server()

    transport = FastMCPTransport(
        mcp=server
    )

    async with transport.connect_session() as session:

        await session.initialize()

        yield session
