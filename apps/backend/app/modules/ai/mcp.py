from __future__ import annotations

import logging
import math
import re
import threading
from collections import Counter
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
_tool_index: ToolRetriever | None = None
_catalog_cache: list[dict[str, Any]] | None = None
_tool_index_lock = threading.Lock()

fastmcp.settings.log_enabled = False

_logger = logging.getLogger("fastmcp")
_logger.handlers.clear()
_logger.propagate = False
_logger.setLevel(logging.CRITICAL)

_MCP_TOOL_METHODS = {"get", "post", "put", "patch", "delete"}


def init_mcp(app: FastAPI) -> None:
    global _backend_app, _mcp_server, _tools_cache, _tool_index, _catalog_cache

    _backend_app = app

    # invalida cache caso reload da aplicação aconteça
    _mcp_server = None
    _tools_cache = None
    _tool_index = None
    _catalog_cache = None


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


# ---------------------------------------------------------------------------
# Retrieval-based tool loading
#
# The full MCP tool catalog (every OpenAPI route) is never sent to the model at
# once. Instead each request follows a *select -> load -> execute -> discard*
# cycle:
#   1. a dependency-free BM25 index ranks the tools against the prompt;
#   2. only the top matches have their full JSON schemas materialized;
#   3. tools the model asks for by name but that were not pre-selected are
#      loaded on demand, so nothing is ever fully enumerated upfront;
#   4. everything is scoped to the current request and thrown away afterwards,
#      so no tool knowledge leaks between requests and token usage stays flat.
# ---------------------------------------------------------------------------

_K1 = 1.5
_B = 0.75

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_STOPWORDS = frozenset(
    {
        # english
        "a", "an", "the", "and", "or", "but", "for", "nor", "on", "at", "to",
        "from", "by", "with", "of", "in", "is", "are", "was", "were", "be",
        "been", "being", "have", "has", "had", "does", "did", "will",
        "would", "can", "could", "should", "may", "might", "must", "not",
        "yes", "i", "you", "he", "she", "it", "we", "they", "him",
        "her", "us", "them", "my", "your", "his", "its", "our", "their",
        "this", "that", "these", "those", "as", "so", "than", "then", "if",
        "else", "please", "want", "need", "like", "get", "using", "used",
        "use", "list",
        # portuguese
        "o", "os", "um", "uma", "uns", "umas", "de", "da",
        "dos", "das", "em", "na", "nos", "nas", "para", "por", "com",
        "sem", "e", "ou", "mas", "que", "como", "se", "ao", "aos",
        "nao", "sim", "eu", "voce", "ele", "ela", "eles", "elas", "meu",
        "minha", "meus", "minhas", "seu", "sua", "seus", "suas", "este",
        "esta", "esse", "essa", "aquele", "aquela", "isso", "isto", "quero",
        "preciso", "favor", "pode", "poderia", "gostaria", "mande", "envie",
        "te", "lhe", "qual", "onde", "quando", "porque",
        "saber", "ver", "mostrar", "criar", "fazer",
    }
)


def _tokenize(text: str) -> list[str]:
    return [
        token
        for token in _TOKEN_RE.findall(text.lower())
        if token not in _STOPWORDS and len(token) > 1
    ]


class ToolRetriever:
    """Dependency-free BM25 index over the MCP tool catalog.

    ``tools`` are ``mcp.types.Tool`` objects; the index is built once per app
    reload and is completely token-free, so ranking a prompt costs microseconds.
    """

    def __init__(self, tools: list[Any]):
        self.tools = tools
        self._doc_tokens = [
            _tokenize(f"{tool.name} {tool.description or ''}")
            for tool in tools
        ]
        self._doc_lengths = [len(tokens) for tokens in self._doc_tokens]
        n_docs = len(self.tools)
        self._avgdl = (sum(self._doc_lengths) / n_docs) if n_docs else 0.0

        df: Counter[str] = Counter()
        for tokens in self._doc_tokens:
            df.update(set(tokens))
        self._idf = {
            term: math.log(1 + (n_docs - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }

    def search(self, query: str, *, limit: int) -> list[int]:
        """Return the indices of the ``limit`` most relevant tools."""
        query_terms = _tokenize(query)
        if not query_terms or not self.tools:
            return []

        ranked: list[tuple[float, int]] = []
        for i, tokens in enumerate(self._doc_tokens):
            term_freqs = Counter(tokens)
            doc_len = self._doc_lengths[i]
            score = 0.0
            for term in query_terms:
                idf = self._idf.get(term)
                if idf is None:
                    continue
                freq = term_freqs.get(term, 0)
                if not freq:
                    continue
                length_norm = (
                    doc_len / self._avgdl if self._avgdl else 1.0
                )
                denominator = (
                    freq + _K1 * (1 - _B + _B * length_norm)
                )
                score += idf * (freq * (_K1 + 1)) / denominator
            if score > 0:
                ranked.append((score, i))

        ranked.sort(key=lambda pair: pair[0], reverse=True)
        return [i for _, i in ranked[:limit]]


def _ensure_tool_index() -> ToolRetriever | None:
    global _tool_index
    if _tool_index is None and _tools_cache:
        with _tool_index_lock:
            if _tool_index is None and _tools_cache:
                _tool_index = ToolRetriever(_tools_cache)
    return _tool_index


def select_tool_names(
    query: str,
    *,
    limit: int | None = None,
) -> list[str]:
    """Return the names of the MCP tools most relevant to ``query``.

    The ranking is purely lexical (BM25) and free of model calls. The result is
    scoped to the current request and never cached.
    """
    index = _ensure_tool_index()
    if index is None:
        return []
    limit = limit or settings.AI_TOOL_SELECTION_LIMIT
    if not query or not query.strip():
        return [tool.name for tool in index.tools[:limit]]
    return [index.tools[i].name for i in index.search(query, limit=limit)]


def selection_query_from_items(input_items: list[dict[str, Any]]) -> str:
    """Build a compact retrieval query from the last user/assistant turns."""
    parts: list[str] = []
    for item in reversed(input_items):
        role = item.get("role")
        if role not in ("user", "assistant", "model"):
            continue
        content = item.get("content")
        if isinstance(content, str) and content.strip():
            parts.append(content)
        if len(parts) >= 3:
            break
    return " ".join(reversed(parts))


class ToolSet:
    """Per-request MCP tool loading.

    Implements the *select -> load -> execute -> discard* lifecycle:

    - ``select``: the BM25 index picks the most relevant tools;
    - ``load``: only those tools' full definitions are materialized;
    - ``execute``: ``ensure`` discovers a tool by name on demand (e.g. when the
      model calls one that was not pre-selected) so the model only ever pays
      for the schemas it actually uses;
    - ``discard``: the instance lives for a single request and is dropped,
      keeping no knowledge between calls.
    """

    def __init__(
        self,
        *,
        tools_by_name: dict[str, Any],
        query: str,
        allowed_tools: list[str] | None = None,
        limit: int | None = None,
    ):
        self._tools_by_name = tools_by_name
        self._allowed = None if allowed_tools is None else set(allowed_tools)
        self._active: dict[str, None] = {}
        limit = limit or settings.AI_TOOL_SELECTION_LIMIT
        for name in select_tool_names(query, limit=limit):
            if name in tools_by_name and self.available(name):
                self._active[name] = None
        if not self._active:
            # The model must always have at least a small, deterministic tool
            # set to work with, even when the query has no lexical overlap.
            for name in self._tools_by_name:
                if self.available(name):
                    self._active[name] = None
                if len(self._active) >= limit:
                    break

    def available(self, name: str) -> bool:
        """Whether the tool exists and is allowed in the current scope."""
        if name not in self._tools_by_name:
            return False
        return self._allowed is None or name in self._allowed

    def ensure(self, name: str) -> bool:
        """Load a tool on demand. Returns ``True`` when newly loaded."""
        if name in self._active:
            return False
        if not self.available(name) or not settings.AI_TOOL_ON_DEMAND:
            return False
        self._active[name] = None
        return True

    @property
    def active_names(self) -> list[str]:
        return list(self._active)

    def tools(self) -> list[Any]:
        return [self._tools_by_name[name] for name in self._active]

    def resolve(self, name: str) -> Any | None:
        return self._tools_by_name.get(name)


def _catalog() -> list[dict[str, Any]]:
    global _catalog_cache
    if _catalog_cache is None:
        _catalog_cache = sorted(
            list_mcp_tools(),
            key=lambda tool: tool["name"],
        )
    return _catalog_cache


def build_tool_catalog(
    *,
    allowed_tools: list[str] | None = None,
    limit: int | None = None,
) -> str:
    """Compact one-line-per-tool catalog appended to the instructions.

    Lets the model recognize every available function without paying for the
    full JSON schemas. Tools are sorted by name for stability and capped at
    ``AI_TOOL_CATALOG_LIMIT`` lines to keep the prompt small.
    """
    tools = _catalog()
    if allowed_tools is not None:
        allowed = set(allowed_tools)
        tools = [tool for tool in tools if tool["name"] in allowed]
    limit = limit or settings.AI_TOOL_CATALOG_LIMIT
    if limit and len(tools) > limit:
        tools = tools[:limit]
    if not tools:
        return ""

    lines: list[str] = []
    for tool in tools:
        summary = (tool.get("summary") or "").strip().replace("\n", " ")
        if len(summary) > 90:
            summary = summary[:87].rstrip() + "..."
        lines.append(
            f"- {tool['name']}: {summary}" if summary else f"- {tool['name']}"
        )
    return (
        "Available tools (call a tool only when strictly needed, by its exact "
        f"name):\n{chr(10).join(lines)}"
    )


def find_available_tools(query: str) -> list[dict[str, Any]]:
    """Return compact metadata for the tools most relevant to ``query``."""
    by_name = {tool["name"]: tool for tool in _catalog()}
    return [
        by_name[name]
        for name in select_tool_names(query)
        if name in by_name
    ]


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
        # build the BM25 index once over the freshly listed catalog
        _ensure_tool_index()

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
