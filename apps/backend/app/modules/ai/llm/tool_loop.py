"""Shared parallel tool-call execution for the LLM providers.

A model response can carry several tool calls at once (the responses /
chat-completions loop returns a whole batch before asking for the next turn).
Running them sequentially multiplies the wall-clock latency of a generation by
the number of calls. This helper executes a whole batch concurrently through
the in-process MCP session, preserves the original order, and returns one
serialized result per call so every provider feeds them back to the model in a
single round trip.

It also centralizes the (verbose, development-only) tool logging so the hot
loop never pays for rich formatting in production.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

from rich.syntax import Syntax

from app.core.config import settings
from app.core.logging import console


def ai_logging_enabled() -> bool:
    """Whether to print the per-tool-call debug logs."""
    return settings.AI_DEBUG_LOGGING or settings.ENVIRONMENT.lower() != "production"


async def run_function_calls_parallel(
    *,
    function_calls: list[Any],
    session: Any,
    toolset: Any,
    failed_calls: dict[tuple[str, str], dict[str, object]],
    serialize_result: Callable[[Any], dict[str, object]],
) -> list[tuple[dict[str, object], bool]]:
    """Run a batch of model tool calls concurrently, preserving call order.

    Returns one ``(serialized, is_error)`` tuple per call, aligned with
    ``function_calls``. Failed calls are recorded in ``failed_calls`` so a
    model retry of the exact same call short-circuits instead of re-running it.
    """
    log = ai_logging_enabled()

    async def run_one(function_call: Any) -> tuple[dict[str, object], bool]:
        name = function_call.name
        arguments = function_call.arguments
        is_error = False
        serialized: dict[str, object] = {}

        if not toolset.available(name):
            serialized = {"error": "Tool is not available"}
            if log:
                console.print(
                    f"[yellow]>>> TOOL (unavailable, skipped): {name}[/]"
                )
        elif (name, arguments) in failed_calls:
            serialized = failed_calls[(name, arguments)]
            if log:
                console.print(
                    f"[yellow]>>> TOOL (cached error, skipped): {name}[/]"
                )
        else:
            if toolset.ensure(name) and log:
                console.print(f"[yellow]>>> TOOL (loaded on demand): {name}[/]")
            if log:
                console.print(f"[bold magenta]>>> TOOL: {name}[/]")
            try:
                args = json.loads(arguments or "{}")
                if not isinstance(args, dict):
                    raise TypeError("Tool arguments must be a JSON object")
                if log and args:
                    console.print(
                        Syntax(
                            json.dumps(
                                args, indent=2, ensure_ascii=False
                            ),
                            "json",
                            word_wrap=True,
                            theme="monokai",
                            background_color="default",
                        )
                    )
                result = await session.call_tool(name, args)
                serialized = serialize_result(result)
                is_error = result.isError
                if log:
                    label = "TOOL ERROR" if is_error else "TOOL RESULT"
                    color = "red" if is_error else "green"
                    console.print(f"[bold {color}]<<< {label}: {serialized}[/]")
            except Exception as exc:  # noqa: BLE001 - tool failures feed back to the model
                serialized = {"error": f"{type(exc).__name__}: {exc}"}
                is_error = True
                if log:
                    console.print(f"[bold red]<<< TOOL ERROR: {serialized}[/]")

            if is_error:
                failed_calls[(name, arguments)] = serialized

        return serialized, is_error

    results = await asyncio.gather(*(run_one(fc) for fc in function_calls))
    return list(results)
