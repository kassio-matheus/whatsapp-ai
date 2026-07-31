"""Optional provider adapters supplied by an application."""

from app.modules.whatsapp.adapters import (
    AdapterMessageResult,
    WhatsAppAdapter,
    WhatsAppAdapterRegistry,
    whatsapp_adapter_registry,
)

__all__ = [
    "AdapterMessageResult",
    "WhatsAppAdapter",
    "WhatsAppAdapterRegistry",
    "whatsapp_adapter_registry",
]
