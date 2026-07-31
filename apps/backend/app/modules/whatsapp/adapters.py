"""Provider-agnostic contracts for WhatsApp integrations.

The database stores only the adapter key. A project can register an adapter
for any official API, unofficial client or internal gateway at startup without
changing the WhatsApp domain models or HTTP API.
"""

from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any, Protocol

from .models import IntegrationType, WhatsAppIntegration, WhatsAppMessage


@dataclass(frozen=True)
class AdapterMessageResult:
    """Normalized result returned by an adapter after sending a message."""

    external_id: str | None = None
    status: str = "sent"
    raw: dict[str, Any] | None = None


class WhatsAppAdapter(Protocol):
    """Minimal contract an external WhatsApp library must implement.

    Contact, conversation and message persistence is handled by this module.
    Adapters are responsible only for provider communication, which keeps
    provider-specific payloads outside the normalized database schema.
    """

    name: str
    integration_type: IntegrationType

    def send_message(
        self,
        *,
        integration: WhatsAppIntegration,
        message: WhatsAppMessage,
    ) -> AdapterMessageResult | Awaitable[AdapterMessageResult]:
        """Send a normalized message through the external provider."""


class WhatsAppAdapterRegistry:
    """Runtime registry used by applications to plug in any provider client."""

    def __init__(self) -> None:
        self._adapters: dict[str, WhatsAppAdapter] = {}

    def register(self, adapter: WhatsAppAdapter, *, replace: bool = False) -> None:
        if not adapter.name.strip():
            raise ValueError("WhatsApp adapter name cannot be empty")
        if adapter.name in self._adapters and not replace:
            raise ValueError(f"WhatsApp adapter already registered: {adapter.name}")
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> WhatsAppAdapter:
        try:
            return self._adapters[name]
        except KeyError as exc:
            raise KeyError(f"WhatsApp adapter is not registered: {name}") from exc

    def resolve(self, integration: WhatsAppIntegration) -> WhatsAppAdapter:
        adapter = self.get(integration.adapter)
        if adapter.integration_type != IntegrationType(integration.integration_type):
            raise ValueError(
                "WhatsApp adapter type does not match the integration type: "
                f"{integration.integration_type}"
            )
        return adapter

    def unregister(self, name: str) -> None:
        self._adapters.pop(name, None)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))


whatsapp_adapter_registry = WhatsAppAdapterRegistry()
