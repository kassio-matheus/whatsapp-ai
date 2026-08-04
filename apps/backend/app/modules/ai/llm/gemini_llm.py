"""Google Gemini provider using the native ``google-genai`` client.

Gemini exposes tools through function declarations and returns function calls
as structured parts. The assistant turn (with the requested tool calls) is
appended back to the conversation and followed by a ``user`` turn containing
the tool responses, matching Gemini's multi-turn function-calling contract.
"""

import asyncio
import json
import logging
from typing import Any, ClassVar

from google import genai
from google.genai import types
from mcp.types import Tool as McpTool
from rich.syntax import Syntax

from app.core.logging import console

from ..mcp import (
    ToolSet,
    build_tool_catalog,
    get_tools,
    mcp_session,
    selection_query_from_items,
)
from ..models import AIPlatform, ChatResponseStructure
from .common import parse_chat_response
from .openai_llm import (
    MAX_REMOTE_CALLS,
    SCOPED_TOOL_GUIDANCE,
    TOOL_GUIDANCE,
    OpenAI,
)

_logger = logging.getLogger(__name__)


class Gemini(AIPlatform):
    """Google Gemini LLM provider (native ``google-genai`` client)."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3.5-flash-lite",
        thinking_level: str = "MINIMAL",
        supports_thinking: bool = True,
    ):
        self.api_key = api_key
        self.model = model
        self.thinking_level = thinking_level
        self.supports_thinking = supports_thinking

    def generate(
        self,
        prompt: str,
        context: list[dict[str, str]] | None = None,
        system_prompt: str | None = None,
        auth_token: str | None = None,
        allowed_tools: list[str] | None = None,
    ) -> ChatResponseStructure:
        input_items: list[dict[str, str]] = []

        if context:
            for msg in context:
                input_items.append(
                    {
                        "role": "user" if msg["role"] == "user" else "model",
                        "content": msg["content"],
                    }
                )

        input_items.append({"role": "user", "content": prompt})

        parts = [TOOL_GUIDANCE]
        if allowed_tools is not None:
            parts.append(SCOPED_TOOL_GUIDANCE)
        catalog = build_tool_catalog(allowed_tools=allowed_tools)
        if catalog:
            parts.append(catalog)
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

    #: JSON Schema keys accepted by ``google.genai.types.Schema``. The MCP tool
    #: schemas derived from the backend OpenAPI carry extra keys (``examples``,
    #: ``title``, ``const``…) that the Gemini client rejects, so they must be
    #: stripped before building the function declarations.
    _GEMINI_SCHEMA_FIELDS: ClassVar[set[str]] = {
        "defs",
        "ref",
        "anyOf",
        "default",
        "description",
        "enum",
        "example",
        "format",
        "items",
        "maxItems",
        "maxLength",
        "maxProperties",
        "maximum",
        "minItems",
        "minLength",
        "minProperties",
        "minimum",
        "nullable",
        "pattern",
        "properties",
        "propertyOrdering",
        "required",
        "title",
        "type",
    }

    @classmethod
    def _sanitize_schema(cls, node: Any) -> Any:
        if isinstance(node, dict):
            cleaned: dict[str, Any] = {}
            for key, value in node.items():
                if key == "examples" and isinstance(value, list) and value:
                    cleaned["example"] = cls._sanitize_schema(value[0])
                elif key == "properties" and isinstance(value, dict):
                    cleaned["properties"] = {
                        name: cls._sanitize_schema(prop_schema)
                        for name, prop_schema in value.items()
                    }
                elif key in cls._GEMINI_SCHEMA_FIELDS:
                    cleaned[key] = cls._sanitize_schema(value)
            return cleaned
        if isinstance(node, list):
            return [cls._sanitize_schema(item) for item in node]
        return node

    @classmethod
    def _to_function_declaration(cls, tool: McpTool) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=tool.name,
            description=tool.description or "",
            parameters=cls._sanitize_schema(tool.inputSchema),
        )

    @staticmethod
    def _to_content(item: dict[str, str]) -> types.Content:
        return types.Content(
            role=item["role"],
            parts=[types.Part.from_text(text=item["content"])],
        )

    @staticmethod
    def _parse_response(response: Any) -> ChatResponseStructure:
        return parse_chat_response(response.text or "")

    async def _generate_async(
        self,
        input_items: list[dict[str, str]],
        instruction: str | None,
        actor_user_id: str | None,
        allowed_tools: list[str] | None,
    ) -> ChatResponseStructure:
        client = genai.Client(api_key=self.api_key)
        try:
            return await self._generate_with_client(
                client=client,
                input_items=input_items,
                instruction=instruction,
                actor_user_id=actor_user_id,
                allowed_tools=allowed_tools,
            )
        finally:
            # Explicitly close the client so the library never has to fall back
            # to ``AsyncClient.__del__``, which schedules ``aclose()`` as a
            # fire-and-forget task on the running loop. That task explodes with
            # "Event loop is closed" when the loop (created by ``asyncio.run``)
            # is torn down while the client is still alive.
            client.close()
            try:
                await client.aio.aclose()
            except Exception as exc:  # noqa: BLE001 - cleanup must never mask the result
                _logger.debug("Gemini async client close failed: %s", exc)

    async def _generate_with_client(
        self,
        *,
        client: genai.Client,
        input_items: list[dict[str, str]],
        instruction: str | None,
        actor_user_id: str | None,
        allowed_tools: list[str] | None,
    ) -> ChatResponseStructure:
        contents: list[types.Content] = [
            self._to_content(item) for item in input_items
        ]

        async with mcp_session(actor_user_id=actor_user_id) as session:
            mcp_tools = await get_tools(session)
            toolset = ToolSet(
                tools_by_name={tool.name: tool for tool in mcp_tools},
                query=selection_query_from_items(input_items),
                allowed_tools=allowed_tools,
            )

            base_config_kwargs: dict[str, Any] = {
                "system_instruction": instruction or "",
                "response_mime_type": "application/json",
            }
            if self.supports_thinking:
                base_config_kwargs["thinking_config"] = types.ThinkingConfig(
                    thinking_level=self.thinking_level,
                )

            def build_config() -> types.GenerateContentConfig:
                declarations = [
                    self._to_function_declaration(tool)
                    for tool in toolset.tools()
                ]
                config_kwargs = dict(base_config_kwargs)
                config_kwargs["tools"] = (
                    [types.Tool(function_declarations=declarations)]
                    if declarations
                    else None
                )
                return types.GenerateContentConfig(**config_kwargs)

            no_tools_config = types.GenerateContentConfig(
                **base_config_kwargs
            )

            failed_calls: dict[tuple[str, str], dict[str, object]] = {}
            executed_calls: set[tuple[str, str]] = set()
            looping = False

            async def generate_content(
                current_contents: list[types.Content],
                current_config: types.GenerateContentConfig | None = None,
            ) -> types.GenerateContentResponse:
                return await client.aio.models.generate_content(
                    model=self.model,
                    contents=current_contents,
                    config=current_config or build_config(),
                )

            response = await generate_content(contents)

            for _ in range(MAX_REMOTE_CALLS):
                function_calls = response.function_calls or []
                if not function_calls:
                    break
                if any(
                    (fc.name, json.dumps(dict(fc.args or {}), sort_keys=True))
                    in executed_calls
                    for fc in function_calls
                ):
                    looping = True
                    break

                contents.append(response.candidates[0].content)

                function_responses: list[types.Part] = []
                for function_call in function_calls:
                    name = function_call.name
                    args = dict(function_call.args or {})
                    args_key = json.dumps(args, sort_keys=True)
                    serialized: dict[str, object]
                    is_error = False

                    if not isinstance(name, str) or not toolset.available(name):
                        serialized = {"error": "Tool is not available"}
                        console.print(
                            f"[yellow]>>> TOOL (unavailable, skipped): {name}[/]"
                        )
                    elif (name, args_key) in failed_calls:
                        serialized = failed_calls[(name, args_key)]
                        console.print(
                            f"[yellow]>>> TOOL (cached error, skipped): {name}[/]"
                        )
                    else:
                        toolset.ensure(name)
                        console.print(f"[bold magenta]>>> TOOL: {name}[/]")
                        try:
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
                            failed_calls[(name, args_key)] = serialized
                        else:
                            executed_calls.add((name, args_key))

                    function_responses.append(
                        types.Part.from_function_response(
                            name=name,
                            response=serialized,
                        )
                    )

                contents.append(types.Content(
                    role="user", parts=function_responses))
                response = await generate_content(contents)

            if looping or not (response.text or "").strip():
                for _ in range(2):
                    response = await generate_content(contents, no_tools_config)
                    if (response.text or "").strip():
                        break

        return self._parse_response(response)
