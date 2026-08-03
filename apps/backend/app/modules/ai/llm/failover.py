"""LLM failover: try a chain of providers until one answers.

The default order is DeepSeek, then ChatGPT (OpenAI), then Gemini. Whenever a
provider fails to complete a request, the next one in the chain takes over, so
an outage in a single provider never breaks the chat.
"""

from __future__ import annotations

import logging

from app.core.logging import console
from app.modules.ai.llm.common import friendly_provider_error

from ..models import AIPlatform, ChatResponseStructure

_logger = logging.getLogger(__name__)


class EmptyResponseError(RuntimeError):
    """Raised when a provider completes but returns no usable text."""


class AllProvidersFailed(RuntimeError):
    """Raised when every provider in the chain failed to answer.

    The message lists a human-friendly reason for each provider.
    """

    def __init__(self, failures: list[tuple[str, str]]):
        self.failures = failures
        if failures:
            message = "; ".join(f"{name}: {reason}" for name, reason in failures)
        else:
            message = "No LLM provider is configured"
        super().__init__(message)


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

        failures: list[tuple[str, str]] = []
        for provider in self.providers:
            try:
                console.print(f"[bold cyan]>>> LLM: {type(provider).__name__}[/]")
                result = provider.generate(
                    prompt=prompt,
                    context=context,
                    system_prompt=system_prompt,
                    auth_token=auth_token,
                    allowed_tools=allowed_tools,
                )
                if not (result.response or "").strip():
                    raise EmptyResponseError(
                        f"{type(provider).__name__} returned an empty reply"
                    )
                return result
            except Exception as exc:  # noqa: BLE001 - failover is the point
                failures.append(
                    (type(provider).__name__, friendly_provider_error(exc))
                )
                _logger.warning(
                    "LLM provider %s failed, trying next one: %s",
                    type(provider).__name__,
                    exc,
                )
                console.print(
                    f"[bold red]>>> LLM {type(provider).__name__} failed: "
                    f"{type(exc).__name__}: {exc}[/]"
                )

        raise AllProvidersFailed(failures)
