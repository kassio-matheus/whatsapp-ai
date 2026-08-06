import asyncio
import json
from typing import Any, cast

from mcp.types import CallToolResult
from mcp.types import Tool as McpTool
from openai import AsyncOpenAI, BadRequestError

from app.core.config import settings
from app.core.logging import console
from app.modules.ai.llm.tool_loop import run_function_calls_parallel

from ..mcp import (
    ToolSet,
    get_tools,
    mcp_session,
    selection_query_from_items,
)
from ..models import AIPlatform, ChatResponseStructure
from ..token_saver import (
    compact_prompt,
    model_context_budget,
    trim_context,
)
from .common import tool_name_from_validation_error
from .guidance import (
    build_instruction,
)

MAX_REMOTE_CALLS = 10


async def create_response_with_tool_retry(
    *,
    client: Any,
    input_items: list[dict[str, Any]],
    instruction: str | None,
    tool_definitions: list[dict[str, Any]],
    toolset: ToolSet,
    make_request_kwargs: Any,
    to_tool_definition: Any,
) -> Any:
    """Call ``responses.create`` retrying tool-validation 400s.

    The instruction text lists every tool (the catalog) while ``tools`` only
    carries the BM25-selected subset, so a small model may call a tool that was
    not declared in ``request.tools``. Providers (notably Groq) reject that
    whole request with a 400. On retry the offending tool is ``ensure``d into
    the toolset, declared in ``request.tools`` and the same input replayed.
    ``tool_definitions`` is updated in place so the caller keeps the expanded
    list. Other errors propagate unchanged.
    """
    for _ in range(MAX_REMOTE_CALLS):
        kwargs = make_request_kwargs(
            input_items=input_items,
            instruction=instruction,
            tool_definitions=tool_definitions,
        )
        try:
            return await cast(Any, client.responses.create)(**kwargs)
        except BadRequestError as exc:
            missing = tool_name_from_validation_error(exc)
            if missing is None or not toolset.ensure(missing):
                raise
            tool_definitions[:] = [
                to_tool_definition(tool) for tool in toolset.tools()
            ]
            console.print(
                f"[yellow]>>> TOOL (redeclared and retried): {missing}[/]"
            )
    raise RuntimeError("Tool validation retries exhausted")


class OpenAI(AIPlatform):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5.6-luna",
        reasoning: str = "medium",
        supports_thinking: bool = True,
    ):
        self.api_key = api_key
        self.model = model
        self.reasoning_effort = reasoning
        self.supports_thinking = supports_thinking

    def generate(
        self,
        prompt: str,
        context: list[dict[str, str]] | None = None,
        system_prompt: str | None = None,
        actor_user_id: str | None = None,
        allowed_tools: list[str] | None = None,
    ) -> ChatResponseStructure:
        budget = model_context_budget(self.model)
        context = trim_context(context, max_tokens=budget)
        prompt = compact_prompt(
            prompt,
            max_tokens=max(1, round(budget / 3)),
        )

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

        instruction, _ = build_instruction(
            system_prompt=system_prompt,
            allowed_tools=allowed_tools,
        )

        return asyncio.run(
            self._generate_async(
                input_items=input_items,
                instruction=instruction,
                actor_user_id=actor_user_id,
                allowed_tools=allowed_tools,
            )
        )

    @staticmethod
    def _to_openai_tool(tool: McpTool) -> dict[str, Any]:
        return {
            "type": "function",
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema,
            "strict": False,
        }

    @staticmethod
    def _serialize_tool_result(result: CallToolResult) -> dict[str, object]:
        texts = [getattr(content, "text", "") for content in result.content]
        text = "\n".join(t for t in texts if t)
        return {"error": text} if result.isError else {"result": text}

    @staticmethod
    def _response_item_to_input(item: Any) -> dict[str, Any]:
        return item.model_dump(exclude_none=True)

    @staticmethod
    def _parse_response(response: Any) -> ChatResponseStructure:
        return ChatResponseStructure.model_validate_json(response.output_text or "{}")

    @staticmethod
    def _response_schema() -> dict[str, Any]:
        schema = ChatResponseStructure.model_json_schema()
        schema["additionalProperties"] = False
        return schema

    def _request_kwargs(
        self,
        *,
        input_items: list[dict[str, Any]],
        instruction: str | None,
        tool_definitions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "input": cast(Any, input_items),
            "instructions": instruction,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "chat_response",
                    "schema": self._response_schema(),
                    "strict": True,
                }
            },
            "tools": cast(Any, tool_definitions),
        }
        if self.supports_thinking:
            kwargs["reasoning"] = {"effort": self.reasoning_effort}
        return kwargs

    async def _generate_async(
        self,
        input_items: list[dict[str, Any]],
        instruction: str | None,
        actor_user_id: str | None,
        allowed_tools: list[str] | None,
    ) -> ChatResponseStructure:
        # When no tool is allowed (e.g. WhatsApp auto-reply with
        # ``allowed_tools=[]``) the request never carries tools, so opening the
        # in-process MCP server and listing its tools is pure overhead. Take a
        # single plain generation fast path instead.
        no_tools = allowed_tools is not None and len(allowed_tools) == 0

        async with AsyncOpenAI(
            api_key=self.api_key,
            timeout=settings.AI_PROVIDER_TIMEOUT_SECONDS,
        ) as client:
            if no_tools:
                response = await cast(Any, client.responses.create)(
                    **self._request_kwargs(
                        input_items=input_items,
                        instruction=instruction,
                        tool_definitions=[],
                    )
                )
                return self._parse_response(response)

            async with mcp_session(actor_user_id=actor_user_id) as session:
                mcp_tools = await get_tools(session)
                toolset = ToolSet(
                    tools_by_name={tool.name: tool for tool in mcp_tools},
                    query=selection_query_from_items(input_items),
                    allowed_tools=allowed_tools,
                )
                tool_definitions = [
                    self._to_openai_tool(tool) for tool in toolset.tools()
                ]

                failed_calls: dict[tuple[str, str], dict[str, object]] = {}

                response = await create_response_with_tool_retry(
                    client=client,
                    input_items=input_items,
                    instruction=instruction,
                    tool_definitions=tool_definitions,
                    toolset=toolset,
                    make_request_kwargs=self._request_kwargs,
                    to_tool_definition=self._to_openai_tool,
                )

                for _ in range(MAX_REMOTE_CALLS):
                    function_calls = [
                        item
                        for item in response.output
                        if item.type == "function_call"
                    ]
                    if not function_calls:
                        break

                    results = await run_function_calls_parallel(
                        function_calls=function_calls,
                        session=session,
                        toolset=toolset,
                        failed_calls=failed_calls,
                        serialize_result=self._serialize_tool_result,
                    )
                    tool_definitions[:] = [
                        self._to_openai_tool(tool) for tool in toolset.tools()
                    ]

                    function_outputs: list[dict[str, str]] = [
                        {
                            "type": "function_call_output",
                            "call_id": function_call.call_id,
                            "output": json.dumps(
                                serialized, ensure_ascii=False
                            ),
                        }
                        for function_call, (serialized, _) in zip(
                            function_calls, results
                        )
                    ]

                    input_items = [
                        *input_items,
                        *[self._response_item_to_input(item)
                          for item in response.output],
                        *function_outputs,
                    ]
                    response = await create_response_with_tool_retry(
                        client=client,
                        input_items=input_items,
                        instruction=instruction,
                        tool_definitions=tool_definitions,
                        toolset=toolset,
                        make_request_kwargs=self._request_kwargs,
                        to_tool_definition=self._to_openai_tool,
                    )

                if not (response.output_text or "").strip():
                    response = await cast(Any, client.responses.create)(
                        **self._request_kwargs(
                            input_items=input_items,
                            instruction=instruction,
                            tool_definitions=[],
                        )
                    )

        return self._parse_response(response)
