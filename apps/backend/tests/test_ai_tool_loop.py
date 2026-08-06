"""Regression tests for the shared parallel tool-loop and the no-tools fast path."""

import asyncio
import time
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import AsyncMock, patch

from app.modules.ai.llm.openai_llm import OpenAI
from app.modules.ai.llm.tool_loop import run_function_calls_parallel


class _FakeCall:
    def __init__(self, name: str, call_id: str):
        self.name = name
        self.arguments = "{}"
        self.call_id = call_id
        self.type = "function_call"


class _FakeToolSet:
    def __init__(self, names: list[str]):
        self._names = list(names)

    def available(self, name: str) -> bool:
        return name in self._names

    def ensure(self, name: str) -> bool:
        return False

    def tools(self) -> list[str]:
        return list(self._names)


def _tool_result(text: str):
    content = SimpleNamespace(text=text)
    return SimpleNamespace(isError=False, content=[content])


def test_run_function_calls_parallel_preserves_order_and_runs_concurrently():
    async def scenario() -> None:
        calls = [_FakeCall("a", "c1"), _FakeCall("b", "c2")]

        async def slow_call_tool(name: str, _args: dict) -> object:
            await asyncio.sleep(0.2)
            return _tool_result(f"result-{name}")

        session = AsyncMock()
        session.call_tool = slow_call_tool

        started = time.perf_counter()
        results = await run_function_calls_parallel(
            function_calls=calls,
            session=session,
            toolset=_FakeToolSet(["a", "b"]),
            failed_calls={},
            serialize_result=lambda r: {"result": r.content[0].text},
        )
        elapsed = time.perf_counter() - started

        assert [r[0]["result"] for r in results] == ["result-a", "result-b"]
        assert [r[1] for r in results] == [False, False]
        # 2 calls of 0.2s must run in parallel (~0.2s), not sequentially (~0.4s).
        assert elapsed < 0.35

    asyncio.run(scenario())


def test_run_function_calls_parallel_caches_failed_calls_across_batches():
    async def scenario() -> None:
        calls = [_FakeCall("boom", "c1")]

        async def failing_call_tool(name: str, _args: dict) -> object:
            return SimpleNamespace(isError=True, content=[])

        session = AsyncMock()
        session.call_tool = AsyncMock(side_effect=failing_call_tool)
        failed: dict[tuple[str, str], dict[str, object]] = {}

        # First batch fails and records the failure.
        results = await run_function_calls_parallel(
            function_calls=calls,
            session=session,
            toolset=_FakeToolSet(["boom"]),
            failed_calls=failed,
            serialize_result=lambda r: {"error": "boom"},
        )
        assert results == [({"error": "boom"}, True)]
        assert session.call_tool.await_count == 1

        # A model retry of the exact same call short-circuits (cached error).
        results = await run_function_calls_parallel(
            function_calls=calls,
            session=session,
            toolset=_FakeToolSet(["boom"]),
            failed_calls=failed,
            serialize_result=lambda r: {"error": "boom"},
        )
        assert results == [({"error": "boom"}, False)]
        assert session.call_tool.await_count == 1  # never re-executed

    asyncio.run(scenario())


def test_no_tools_fast_path_skips_mcp_session():
    class _FakeResponse:
        output: ClassVar[list[object]] = []
        output_text = '{"response": "oi"}'

    provider = OpenAI(api_key="test")
    client = AsyncMock()
    client.responses.create.return_value = _FakeResponse()
    client.__aenter__.return_value = client

    async def forbidden_mcp(**kwargs):  # pragma: no cover - must not be called
        raise AssertionError("MCP must not be opened in the no-tools fast path")

    async def scenario() -> None:
        with (
            patch(
                "app.modules.ai.llm.openai_llm.AsyncOpenAI",
                return_value=client,
            ),
            patch(
                "app.modules.ai.llm.openai_llm.mcp_session",
                side_effect=forbidden_mcp,
            ),
        ):
            result = await provider._generate_async(
                input_items=[{"role": "user", "content": "quanto custa?"}],
                instruction="assistant",
                actor_user_id="u1",
                allowed_tools=[],
            )
            assert result.response == "oi"

    asyncio.run(scenario())
