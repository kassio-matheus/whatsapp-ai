"""Process-local real-time events for the WhatsApp inbox.

The event payload intentionally contains only identifiers and the event name.
Clients re-read the scoped REST resource with their bearer token, so secrets and
provider payloads never cross the event stream.
"""

from __future__ import annotations

import queue
import threading
import uuid
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class WhatsAppEvent:
    type: str
    company_id: str
    instance_id: str | None = None
    conversation_id: str | None = None
    message_id: str | None = None
    occurred_at: str = ""

    def payload(self) -> dict[str, str | None]:
        return asdict(self)


class WhatsAppEventBroker:
    """Fan out events to active browser streams in this API process."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[queue.Queue[WhatsAppEvent]]] = defaultdict(set)
        self._lock = threading.Lock()

    def publish(
        self,
        *,
        company_id: uuid.UUID,
        event_type: str,
        instance_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None,
        message_id: uuid.UUID | None = None,
    ) -> None:
        event = WhatsAppEvent(
            type=event_type,
            company_id=str(company_id),
            instance_id=str(instance_id) if instance_id else None,
            conversation_id=str(conversation_id) if conversation_id else None,
            message_id=str(message_id) if message_id else None,
            occurred_at=datetime.now(UTC).isoformat(),
        )
        with self._lock:
            subscribers = tuple(self._subscribers.get(event.company_id, ()))
        for subscriber in subscribers:
            try:
                subscriber.put_nowait(event)
            except queue.Full:
                # A slow browser will reconcile from REST after its next event.
                continue

    @contextmanager
    def subscribe(self, company_id: uuid.UUID) -> Iterator[queue.Queue[WhatsAppEvent]]:
        subscriber: queue.Queue[WhatsAppEvent] = queue.Queue(maxsize=100)
        company_key = str(company_id)
        with self._lock:
            self._subscribers[company_key].add(subscriber)
        try:
            yield subscriber
        finally:
            with self._lock:
                subscribers = self._subscribers.get(company_key)
                if subscribers is not None:
                    subscribers.discard(subscriber)
                    if not subscribers:
                        self._subscribers.pop(company_key, None)


whatsapp_event_broker = WhatsAppEventBroker()
