import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Notification(SQLModel, table=True):
    """An in-app notification for the current company's operators.

    Unlike ephemeral SSE events, notifications are persisted and exposed
    through a REST endpoint so they survive page reloads and can be listed
    from the dashboard bell.
    """

    __tablename__ = "notifications"

    id: uuid.UUID = SQLField(default_factory=uuid.uuid4, primary_key=True)
    company_id: uuid.UUID = SQLField(
        foreign_key="companies.id", nullable=False, index=True
    )
    type: str = SQLField(max_length=64, index=True)
    title: str = SQLField(max_length=255)
    body: str | None = SQLField(default=None, max_length=2048)
    conversation_id: uuid.UUID | None = SQLField(
        foreign_key="whatsapp_conversations.id", default=None, index=True
    )
    integration_id: uuid.UUID | None = SQLField(
        foreign_key="whatsapp_integrations.id", default=None, index=True
    )
    message_id: uuid.UUID | None = SQLField(
        foreign_key="whatsapp_messages.id", default=None
    )
    is_read: bool = SQLField(default=False, index=True)
    created_at: datetime = SQLField(default_factory=_utcnow, index=True)


class NotificationResponse(BaseModel):
    """A single notification, safe to return to the frontend."""

    id: uuid.UUID
    type: str
    title: str
    body: str | None
    conversation_id: uuid.UUID | None
    integration_id: uuid.UUID | None
    message_id: uuid.UUID | None
    is_read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    """Page of notifications plus the unread count for the header badge."""

    items: list[NotificationResponse]
    unread_count: int


class UnreadCountResponse(BaseModel):
    unread_count: int = Field(description="Number of unread notifications.")
