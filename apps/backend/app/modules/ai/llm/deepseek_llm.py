"""DeepSeek chat completion provider.

Uses the native OpenAI SDK pointed at DeepSeek's OpenAI-compatible endpoint
(``https://api.deepseek.com``). It mirrors the tool-calling loop used by the
ChatGPT provider so that MCP tools exposed by the backend work identically.
"""

import asyncio
import json
from typing import Any, cast

from openai import AsyncOpenAI
from rich.syntax import Syntax

from app.core.logging import console

from ..mcp import mcp_session
from ..models import AIPlatform, ChatResponseStructure
from .common import parse_chat_response
from .openai_llm import (
    MAX_REMOTE_CALLS,
    SCOPED_TOOL_GUIDANCE,
    TOOL_GUIDANCE,
    OpenAI,
)


class DeepSeek(AIPlatform):
    """DeepSeek LLM provider (Chat Completions API)."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com"
        self.model = "deepseek-v4-pro"
        self.reasoning_effort = "high"

    def generate(
        self,
        prompt: str,
        context: list[dict[str, str]] | None = None,
        system_prompt: str | None = None,
        auth_token: str | None = None,
        allowed_tools: list[str] | None = None,
    ) -> ChatResponseStructure:
        input_items: list[dict[str, Any]] = []

        if context:
            for msg in context:
                input_items.append(
                    {
                        "role": "user" if msg["role"] == "user" else "assistant",
                        "content": msg["content"],
                    }
                )

        input_items.append({"role": "user", "content": prompt})

        parts = [TOOL_GUIDANCE]
        if allowed_tools is not None:
            parts.append(SCOPED_TOOL_GUIDANCE)
        if system_prompt:
            parts.append(system_prompt)
        instruction = "\n\n".join(parts)

        return asyncio.run(
            self._generate_async(
                input_items=input_items,
                instruction=instruction,
                auth_token=auth_token,
                allowed_tools=allowed_tools,
            )
        )

    @staticmethod
    def _merge_messages(
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Join consecutive messages of the same role.

        The OpenAI-compatible chat API does not accept two consecutive
        ``user`` turns, which can happen when conversation history ends with a
        user message and the prompt is appended right after.
        """
        merged: list[dict[str, Any]] = []
        for message in messages:
            if (
                merged
                and merged[-1]["role"] == message["role"]
                and isinstance(merged[-1].get("content"), str)
            ):
                merged[-1]["content"] += f"\n\n{message['content']}"
            else:
                merged.append(dict(message))
        return merged

    @staticmethod
    def _parse_response(response: Any) -> ChatResponseStructure:
        text = response.choices[0].message.content or ""
        return parse_chat_response(text)

    async def _generate_async(
        self,
        input_items: list[dict[str, Any]],
        instruction: str | None,
        auth_token: str | None,
        allowed_tools: list[str] | None,
    ) -> ChatResponseStructure:
        messages: list[dict[str, Any]] = self._merge_messages(
            [{"role": "system", "content": instruction or ""}]
            + [
                {"role": item["role"], "content": item["content"]}
                for item in input_items
            ]
        )

        async with (
            AsyncOpenAI(api_key=self.api_key, base_url=self.base_url) as client,
            mcp_session(auth_token=auth_token) as session,
        ):
            mcp_tools = (await session.list_tools()).tools
            if allowed_tools is not None:
                allowed_names = set(allowed_tools)
                mcp_tools = [tool for tool in mcp_tools if tool.name in allowed_names]
                allowed_tool_names = allowed_names
            else:
                allowed_tool_names = {tool.name for tool in mcp_tools}
            tool_definitions = [OpenAI._to_openai_tool(tool) for tool in mcp_tools]

            failed_calls: dict[tuple[str, str], dict[str, object]] = {}

            request: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "reasoning_effort": self.reasoning_effort,
                "extra_body": {"thinking": {"type": "enabled"}},
            }
            if tool_definitions:
                request["tools"] = tool_definitions

            response = await cast(Any, client.chat.completions.create)(**request)

            for _ in range(MAX_REMOTE_CALLS):
                choice = response.choices[0].message
                tool_calls = getattr(choice, "tool_calls", None) or []
                if not tool_calls:
                    break

                messages.append(
                    {
                        "role": "assistant",
                        "content": choice.content,
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "type": "function",
                                "function": {
                                    "name": tool_call.function.name,
                                    "arguments": tool_call.function.arguments,
                                },
                            }
                            for tool_call in tool_calls
                        ],
                    }
                )

                function_outputs: list[dict[str, str]] = []
                for tool_call in tool_calls:
                    name = tool_call.function.name
                    arguments = tool_call.function.arguments
                    serialized: dict[str, object]
                    is_error = False

                    if name not in allowed_tool_names:
                        serialized = {"error": "Tool is not available"}
                        console.print(
                            f"[yellow]>>> TOOL (unavailable, skipped): {name}[/]"
                        )
                    elif (name, arguments) in failed_calls:
                        serialized = failed_calls[(name, arguments)]
                        console.print(
                            f"[yellow]>>> TOOL (cached error, skipped): {name}[/]"
                        )
                    else:
                        console.print(f"[bold magenta]>>> TOOL: {name}[/]")
                        try:
                            args = json.loads(arguments or "{}")
                            if not isinstance(args, dict):
                                raise TypeError(
                                    "Tool arguments must be a JSON object"
                                )
                            if args:
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
                            serialized = OpenAI._serialize_tool_result(result)
                            is_error = result.isError
                            if is_error:
                                console.print(
                                    f"[bold red]<<< TOOL ERROR: {serialized}[/]"
                                )
                            else:
                                console.print(
                                    f"[bold green]<<< TOOL RESULT: {serialized}[/]"
                                )
                        except Exception as exc:  # noqa: BLE001 - tool failures feed back to the model
                            serialized = {
                                "error": f"{type(exc).__name__}: {exc}"
                            }
                            is_error = True
                            console.print(
                                f"[bold red]<<< TOOL ERROR: {serialized}[/]"
                            )

                        if is_error:
                            failed_calls[(name, arguments)] = serialized

                    function_outputs.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(serialized, ensure_ascii=False),
                        }
                    )

                messages.extend(function_outputs)
                response = await cast(Any, client.chat.completions.create)(
                    **{**request, "messages": messages}
                )

        return self._parse_response(response)
