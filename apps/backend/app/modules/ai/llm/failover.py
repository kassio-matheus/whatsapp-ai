"""LLM failover: try a chain of providers until one answers.

The default order is DeepSeek, then ChatGPT (OpenAI), then Gemini. Whenever a
provider fails to complete a request, the next one in the chain takes over, so
an outage in a single provider never breaks the chat.
"""

from __future__ import annotations

import logging

from app.core.logging import console

from ..models import AIPlatform, ChatResponseStructure

_logger = logging.getLogger(__name__)


class FailoverLLM(AIPlatform):
    """Wrap an ordered list of ``AIPlatform`` providers with failover."""

    def __init__(self, providers: list[AIPlatform]):
        self.providers = providers

    def generate(
        self,
        prompt: str,
        context: list[dict[str, str]] | None = None,
        system_prompt: str | None = None,
        auth_token: str | None = None,
        allowed_tools: list[str] | None = None,
    ) -> ChatResponseStructure:
        if not self.providers:
            raise RuntimeError("No LLM provider is configured")

        last_error: Exception | None = None
        for provider in self.providers:
            try:
                console.print(f"[bold cyan]>>> LLM: {type(provider).__name__}[/]")
                return provider.generate(
                    prompt=prompt,
                    context=context,
                    system_prompt=system_prompt,
                    auth_token=auth_token,
                    allowed_tools=allowed_tools,
                )
            except Exception as exc:  # noqa: BLE001 - failover is the point
                last_error = exc
                _logger.warning(
                    "LLM provider %s failed, trying next one: %s",
                    type(provider).__name__,
                    exc,
                )
                console.print(
                    f"[bold red]>>> LLM {type(provider).__name__} failed: "
                    f"{type(exc).__name__}: {exc}[/]"
                )

        if last_error is not None:
            raise last_error
        raise RuntimeError("All LLM providers failed")
