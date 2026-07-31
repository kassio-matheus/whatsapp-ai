from .adapters import (
    AdapterMessageResult,
    WhatsAppAdapter,
    WhatsAppAdapterRegistry,
    whatsapp_adapter_registry,
)
from .cloud_api import MetaCloudApiAdapter
from .models import *

whatsapp_adapter_registry.register(MetaCloudApiAdapter(), replace=True)

__all__ = [
    "AdapterMessageResult",
    "MetaCloudApiAdapter",
    "WhatsAppAdapter",
    "WhatsAppAdapterRegistry",
    "whatsapp_adapter_registry",
]
