"""Settings and contracts for the WhatsApp AI auto-responder.

The module bridges the AI stack (LLM + MCP tools) with the WhatsApp inbox so a
company can let the assistant answer inbound messages automatically, with two
MCP degrees:

* **System owner / trusted numbers**: full access to every MCP tool.
* **Regular contacts**: access only to the tools whitelisted by the owner.

Everything is configurable: activation is global (per company) and can be
overridden conversation by conversation.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import JSON, Column
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel


class WhatsAppAISettings(SQLModel, table=True):
    """Per-company configuration for the WhatsApp AI assistant."""

    __tablename__ = "whatsapp_ai_settings"

    company_id: uuid.UUID = SQLField(foreign_key="companies.id", primary_key=True)
    enabled: bool = SQLField(default=False)
    system_prompt: str | None = SQLField(default=None, max_length=16000)
    trusted_phone_numbers: list[str] = SQLField(
        default_factory=list,
        sa_column=Column("trusted_phone_numbers", JSON, nullable=False),
    )
    allowed_contact_tools: list[str] = SQLField(
        default_factory=list,
        sa_column=Column("allowed_contact_tools", JSON, nullable=False),
    )
    reply_cooldown_seconds: int = SQLField(default=20)
    created_at: datetime = SQLField(default_factory=datetime.now)
    updated_at: datetime = SQLField(default_factory=datetime.now)


class ConversationAISetting(SQLModel, table=True):
    """Per-conversation override for the WhatsApp AI assistant.

    ``enabled`` is a tri-state: ``None`` follows the company setting, ``True``
    forces it on and ``False`` forces it off for that conversation.
    """

    __tablename__ = "whatsapp_conversation_ai_settings"

    conversation_id: uuid.UUID = SQLField(
        foreign_key="whatsapp_conversations.id", primary_key=True
    )
    enabled: bool | None = SQLField(default=None)
    system_prompt: str | None = SQLField(default=None, max_length=16000)
    created_at: datetime = SQLField(default_factory=datetime.now)
    updated_at: datetime = SQLField(default_factory=datetime.now)


class WhatsAppAISettingsUpdate(BaseModel):
    """Payload for updating the company-level WhatsApp AI settings."""

    enabled: bool | None = Field(
        default=None, description="Global switch for automatic AI replies."
    )
    system_prompt: str | None = Field(
        default=None,
        max_length=16000,
        description="System prompt steering automatic AI replies.",
    )
    trusted_phone_numbers: list[str] | None = Field(
        default=None,
        description=(
            "Phone numbers treated as system owners. Conversations started by "
            "these numbers give the AI full MCP access."
        ),
    )
    allowed_contact_tools: list[str] | None = Field(
        default=None,
        description=(
            "MCP tool names contacts may use. Empty means contacts get no "
            "backend tools and the AI only answers with text."
        ),
    )
    reply_cooldown_seconds: int | None = Field(
        default=None,
        ge=0,
        le=3600,
        description="Minimum seconds between two automatic replies in a conversation.",
    )


class WhatsAppAISettingsResponse(BaseModel):
    """Company-level WhatsApp AI settings returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    company_id: uuid.UUID = Field(description="Owning company identifier.")
    enabled: bool = Field(description="Global switch for automatic AI replies.")
    system_prompt: str | None = Field(
        description="System prompt steering automatic AI replies."
    )
    trusted_phone_numbers: list[str] = Field(
        description="Phone numbers treated as system owners."
    )
    allowed_contact_tools: list[str] = Field(
        description="MCP tool names contacts are allowed to use."
    )
    reply_cooldown_seconds: int = Field(
        description="Minimum seconds between automatic replies."
    )
    updated_at: datetime = Field(description="Last update timestamp.")


class ConversationAISettingsUpdate(BaseModel):
    """Payload for updating a conversation's AI override."""

    enabled: bool | None = Field(
        default=None,
        description=(
            "Force the AI on/off for this conversation. `null` follows the "
            "company setting."
        ),
    )
    system_prompt: str | None = Field(
        default=None,
        max_length=16000,
        description="Per-conversation system prompt override.",
    )


class ConversationAISettingsResponse(BaseModel):
    """A conversation's AI override returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    conversation_id: uuid.UUID = Field(description="Conversation identifier.")
    enabled: bool | None = Field(
        description="`null` follows the company setting, otherwise the override."
    )
    system_prompt: str | None = Field(
        description="Per-conversation system prompt override, if any."
    )


class McpToolInfo(BaseModel):
    """A single MCP tool exposed by the backend, used to scope contacts."""

    name: str = Field(description="Stable MCP tool name.")
    method: str = Field(description="HTTP method of the underlying route.")
    path: str = Field(description="HTTP path of the underlying route.")
    summary: str | None = Field(default=None, description="Route summary.")
    description: str = Field(description="Longer route description.")
    requires_auth: bool = Field(
        description="Whether the route needs a bearer token."
    )


class McpToolsPage(BaseModel):
    """The full list of MCP tools plus the currently allowed subset."""

    tools: list[McpToolInfo] = Field(description="Every tool the backend exposes.")
    allowed: list[str] = Field(
        description="Tool names currently allowed for WhatsApp contacts."
    )
