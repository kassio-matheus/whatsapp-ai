import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel


class IntegrationType(str, Enum):
    """The WhatsApp API family used by an integration."""

    OFFICIAL = "official"
    UNOFFICIAL = "unofficial"


class MessageDirection(str, Enum):
    """Direction of a message relative to the company."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class ConversationStatus(str, Enum):
    """Lifecycle state of a conversation."""

    OPEN = "open"
    PENDING = "pending"
    CLOSED = "closed"


class MessageStatus(str, Enum):
    """Delivery lifecycle of a message."""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


INTERNAL_MESSAGE_TYPES: tuple[str, ...] = (
    "system",
    "reaction",
    "template",
    "unknown",
    "ephemeral",
)


class WhatsAppIntegration(SQLModel, table=True):
    """A provider-agnostic WhatsApp connection owned by a company."""

    __tablename__ = "whatsapp_integrations"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "name",
            name="uq_whatsapp_integrations_company_name",
        ),
    )

    id: uuid.UUID = SQLField(default_factory=uuid.uuid4, primary_key=True)
    company_id: uuid.UUID = SQLField(
        foreign_key="companies.id", nullable=False, index=True
    )
    name: str = SQLField(max_length=255)
    integration_type: str = SQLField(max_length=16)
    adapter: str = SQLField(max_length=128)
    phone_number: str | None = SQLField(default=None, max_length=64)
    external_account_id: str | None = SQLField(default=None, max_length=255)
    credentials_json: dict[str, Any] = SQLField(
        default_factory=dict,
        sa_column=Column("credentials", JSON, nullable=False),
    )
    config_json: dict[str, Any] = SQLField(
        default_factory=dict,
        sa_column=Column("config", JSON, nullable=False),
    )
    is_active: bool = SQLField(default=True)
    created_at: datetime = SQLField(default_factory=datetime.now)
    updated_at: datetime = SQLField(default_factory=datetime.now)


class WhatsAppContact(SQLModel, table=True):
    """A normalized contact that can be used by any WhatsApp adapter."""

    __tablename__ = "whatsapp_contacts"
    __table_args__ = (
        UniqueConstraint(
            "integration_id",
            "external_id",
            name="uq_whatsapp_contacts_integration_external_id",
        ),
    )

    id: uuid.UUID = SQLField(default_factory=uuid.uuid4, primary_key=True)
    company_id: uuid.UUID = SQLField(
        foreign_key="companies.id", nullable=False, index=True
    )
    integration_id: uuid.UUID = SQLField(
        foreign_key="whatsapp_integrations.id", nullable=False, index=True
    )
    external_id: str | None = SQLField(default=None, max_length=255)
    phone_number: str = SQLField(max_length=64)
    name: str | None = SQLField(default=None, max_length=255)
    profile_picture_url: str | None = SQLField(default=None, max_length=2048)
    is_blocked: bool = SQLField(default=False)
    metadata_json: dict[str, Any] = SQLField(
        default_factory=dict,
        sa_column=Column("metadata", JSON, nullable=False),
    )
    is_active: bool = SQLField(default=True)
    created_at: datetime = SQLField(default_factory=datetime.now)
    updated_at: datetime = SQLField(default_factory=datetime.now)


class WhatsAppConversation(SQLModel, table=True):
    """A conversation normalized independently of a provider's chat object."""

    __tablename__ = "whatsapp_conversations"
    __table_args__ = (
        UniqueConstraint(
            "integration_id",
            "external_id",
            name="uq_whatsapp_conversations_integration_external_id",
        ),
    )

    id: uuid.UUID = SQLField(default_factory=uuid.uuid4, primary_key=True)
    company_id: uuid.UUID = SQLField(
        foreign_key="companies.id", nullable=False, index=True
    )
    integration_id: uuid.UUID = SQLField(
        foreign_key="whatsapp_integrations.id", nullable=False, index=True
    )
    contact_id: uuid.UUID | None = SQLField(
        default=None,
        foreign_key="whatsapp_contacts.id",
        index=True,
    )
    external_id: str | None = SQLField(default=None, max_length=255)
    title: str | None = SQLField(default=None, max_length=255)
    status: str = SQLField(default=ConversationStatus.OPEN.value, max_length=16)
    metadata_json: dict[str, Any] = SQLField(
        default_factory=dict,
        sa_column=Column("metadata", JSON, nullable=False),
    )
    last_message_at: datetime | None = SQLField(default=None, index=True)
    is_active: bool = SQLField(default=True)
    created_at: datetime = SQLField(default_factory=datetime.now)
    updated_at: datetime = SQLField(default_factory=datetime.now)


class WhatsAppMessage(SQLModel, table=True):
    """A normalized message. Provider-specific payloads live in metadata."""

    __tablename__ = "whatsapp_messages"
    __table_args__ = (
        UniqueConstraint(
            "integration_id",
            "external_id",
            name="uq_whatsapp_messages_integration_external_id",
        ),
    )

    id: uuid.UUID = SQLField(default_factory=uuid.uuid4, primary_key=True)
    company_id: uuid.UUID = SQLField(
        foreign_key="companies.id", nullable=False, index=True
    )
    integration_id: uuid.UUID = SQLField(
        foreign_key="whatsapp_integrations.id", nullable=False, index=True
    )
    conversation_id: uuid.UUID = SQLField(
        foreign_key="whatsapp_conversations.id", nullable=False, index=True
    )
    external_id: str | None = SQLField(default=None, max_length=255)
    direction: str = SQLField(max_length=16)
    message_type: str = SQLField(default="text", max_length=32)
    content: str | None = SQLField(default=None, max_length=65535)
    media_url: str | None = SQLField(default=None, max_length=2048)
    status: str = SQLField(default=MessageStatus.PENDING.value, max_length=16)
    metadata_json: dict[str, Any] = SQLField(
        default_factory=dict,
        sa_column=Column("metadata", JSON, nullable=False),
    )
    sent_at: datetime | None = SQLField(default=None)
    is_active: bool = SQLField(default=True)
    created_at: datetime = SQLField(default_factory=datetime.now)
    updated_at: datetime = SQLField(default_factory=datetime.now)


class WhatsAppIntegrationCreate(BaseModel):
    """Payload for registering a WhatsApp integration."""

    company_id: uuid.UUID = Field(description="Company that owns the integration.")
    name: str = Field(
        min_length=1,
        max_length=255,
        description="Unique name for this integration within the company.",
        json_schema_extra={"examples": ["Production WhatsApp"]},
    )
    integration_type: IntegrationType = Field(
        description="Whether the integration uses an official or unofficial API."
    )
    adapter: str = Field(
        min_length=1,
        max_length=128,
        description="Application-defined adapter key used to reach the provider.",
        json_schema_extra={"examples": ["meta-graph"]},
    )
    phone_number: str | None = Field(
        default=None,
        max_length=64,
        description="Phone number bound to the integration.",
        json_schema_extra={"examples": ["+12025550123"]},
    )
    external_account_id: str | None = Field(
        default=None,
        max_length=255,
        description="Provider-side account or app identifier.",
        json_schema_extra={"examples": ["wa-account-98765"]},
    )
    credentials: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider credentials (token, secret). Never returned by the API.",
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Adapter-specific configuration as key/value pairs.",
    )


class WhatsAppIntegrationUpdate(BaseModel):
    """Payload for updating a WhatsApp integration."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    integration_type: IntegrationType | None = None
    adapter: str | None = Field(default=None, min_length=1, max_length=128)
    phone_number: str | None = Field(default=None, max_length=64)
    external_account_id: str | None = Field(default=None, max_length=255)
    credentials: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    is_active: bool | None = None


class WhatsAppIntegrationResponse(BaseModel):
    """WhatsApp integration data returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Integration identifier.")
    company_id: uuid.UUID = Field(description="Owning company identifier.")
    name: str = Field(description="Integration name.")
    integration_type: IntegrationType = Field(description="Official or unofficial API.")
    adapter: str = Field(description="Application-defined adapter key.")
    phone_number: str | None = Field(description="Bound phone number, if any.")
    external_account_id: str | None = Field(description="Provider account identifier.")
    config: dict[str, Any] = Field(description="Adapter-specific configuration.")
    credentials_configured: bool = Field(
        description="Whether credentials were supplied for this integration."
    )
    is_active: bool = Field(description="Whether the integration is active.")
    created_at: datetime = Field(description="Creation timestamp.")
    updated_at: datetime = Field(description="Last update timestamp.")


class WhatsAppCloudApiCredentials(BaseModel):
    """Credentials and identifiers required by Meta's Cloud API."""

    model_config = ConfigDict(extra="forbid")

    app_id: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^\d+$",
        description="Meta app ID.",
        json_schema_extra={"examples": ["123456789012345"]},
    )
    app_secret: str = Field(
        min_length=1,
        max_length=512,
        repr=False,
        description="Meta app secret. Used to validate webhook signatures.",
    )
    access_token: str = Field(
        min_length=1,
        max_length=4096,
        repr=False,
        description=(
            "Meta user or system-user access token with WhatsApp permissions."
        ),
    )
    business_account_id: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^\d+$",
        description="WhatsApp Business Account (WABA) ID.",
        json_schema_extra={"examples": ["102030405060708"]},
    )
    phone_number_id: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^\d+$",
        description="Meta phone number ID, not the formatted phone number.",
        json_schema_extra={"examples": ["109876543210987"]},
    )
    webhook_verify_token: str = Field(
        min_length=1,
        max_length=512,
        repr=False,
        description=(
            "Secret chosen by the application and configured in Meta Webhooks."
        ),
    )
    api_version: str = Field(
        default="v25.0",
        pattern=r"^v\d+\.\d+$",
        description="Graph API version used for this connection.",
        json_schema_extra={"examples": ["v25.0"]},
    )

    @field_validator(
        "app_id",
        "app_secret",
        "access_token",
        "business_account_id",
        "phone_number_id",
        "webhook_verify_token",
        "api_version",
        mode="before",
    )
    @classmethod
    def strip_values(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        return value.strip()


class WhatsAppCloudApiCreate(BaseModel):
    """Payload for creating and verifying a Meta Cloud API connection."""

    company_id: uuid.UUID = Field(description="Company that owns the connection.")
    name: str = Field(
        min_length=1,
        max_length=255,
        description="Friendly name for the WhatsApp channel.",
        json_schema_extra={"examples": ["Support WhatsApp"]},
    )
    credentials: WhatsAppCloudApiCredentials
    subscribe_to_webhooks: bool = Field(
        default=True,
        description=(
            "Subscribe the Meta app to this WABA after credentials are verified."
        ),
    )


class WhatsAppCloudApiUpdate(BaseModel):
    """Payload for updating and re-verifying a Meta Cloud API connection."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    credentials: WhatsAppCloudApiCredentials
    subscribe_to_webhooks: bool = True


class WhatsAppCloudApiConnectionInfo(BaseModel):
    """Non-secret connection data returned after talking to Meta."""

    app_id: str = Field(description="Verified Meta app ID.")
    business_account_id: str = Field(description="Verified WABA ID.")
    business_account_name: str | None = Field(
        description="WABA name returned by Meta, if available."
    )
    phone_number_id: str = Field(description="Verified Meta phone number ID.")
    display_phone_number: str | None = Field(
        description="Formatted phone number returned by Meta, if available."
    )
    verified_name: str | None = Field(
        description="Verified display name returned by Meta, if available."
    )
    quality_rating: str | None = Field(
        description="Meta quality rating for the phone number, if available."
    )
    webhook_subscribed: bool = Field(
        description="Whether this app was subscribed to the WABA in this operation."
    )
    coexistence: Literal[False] = Field(
        default=False,
        description="This connector never uses WhatsApp Business App coexistence.",
    )


class WhatsAppCloudApiConnectResponse(BaseModel):
    """Response for a verified Meta Cloud API connection."""

    integration: WhatsAppIntegrationResponse
    connection: WhatsAppCloudApiConnectionInfo


class WhatsAppContactCreate(BaseModel):
    """Payload for creating a WhatsApp contact."""

    integration_id: uuid.UUID = Field(description="Integration the contact belongs to.")
    external_id: str | None = Field(
        default=None,
        max_length=255,
        description="Provider-side contact identifier.",
        json_schema_extra={"examples": ["wa-contact-00123"]},
    )
    phone_number: str = Field(
        min_length=1,
        max_length=64,
        description="Contact phone number in E.164 format.",
        json_schema_extra={"examples": ["+5521987654321"]},
    )
    name: str | None = Field(
        default=None,
        max_length=255,
        description="Display name of the contact.",
        json_schema_extra={"examples": ["Jane Doe"]},
    )
    profile_picture_url: str | None = Field(
        default=None,
        max_length=2048,
        description="URL of the contact's profile picture.",
    )
    is_blocked: bool = Field(
        default=False, description="Whether the contact is blocked."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Optional key/value metadata."
    )


class WhatsAppContactUpdate(BaseModel):
    """Payload for updating a WhatsApp contact."""

    external_id: str | None = Field(default=None, max_length=255)
    phone_number: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, max_length=255)
    profile_picture_url: str | None = Field(default=None, max_length=2048)
    is_blocked: bool | None = None
    metadata: dict[str, Any] | None = None
    is_active: bool | None = None


class WhatsAppContactResponse(BaseModel):
    """WhatsApp contact data returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Contact identifier.")
    company_id: uuid.UUID = Field(description="Owning company identifier.")
    integration_id: uuid.UUID = Field(description="Integration identifier.")
    external_id: str | None = Field(description="Provider-side contact identifier.")
    phone_number: str = Field(description="Contact phone number.")
    name: str | None = Field(description="Contact display name.")
    profile_picture_url: str | None = Field(description="Profile picture URL.")
    is_blocked: bool = Field(description="Whether the contact is blocked.")
    metadata: dict[str, Any] = Field(description="Key/value metadata.")
    is_active: bool = Field(description="Whether the contact is active.")
    created_at: datetime = Field(description="Creation timestamp.")
    updated_at: datetime = Field(description="Last update timestamp.")


class WhatsAppConversationCreate(BaseModel):
    """Payload for creating a WhatsApp conversation."""

    integration_id: uuid.UUID = Field(description="Integration the conversation uses.")
    contact_id: uuid.UUID | None = Field(
        default=None, description="Associated contact, if any."
    )
    external_id: str | None = Field(
        default=None,
        max_length=255,
        description="Provider-side conversation identifier.",
        json_schema_extra={"examples": ["wa-chat-00456"]},
    )
    title: str | None = Field(
        default=None,
        max_length=255,
        description="Human-friendly conversation title.",
        json_schema_extra={"examples": ["Support - Jane Doe"]},
    )
    status: ConversationStatus = Field(
        default=ConversationStatus.OPEN, description="Conversation status."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Optional key/value metadata."
    )


class WhatsAppConversationUpdate(BaseModel):
    """Payload for updating a WhatsApp conversation."""

    contact_id: uuid.UUID | None = None
    external_id: str | None = Field(default=None, max_length=255)
    title: str | None = Field(default=None, max_length=255)
    status: ConversationStatus | None = None
    metadata: dict[str, Any] | None = None
    is_active: bool | None = None


class WhatsAppConversationResponse(BaseModel):
    """WhatsApp conversation data returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Conversation identifier.")
    company_id: uuid.UUID = Field(description="Owning company identifier.")
    integration_id: uuid.UUID = Field(description="Integration identifier.")
    contact_id: uuid.UUID | None = Field(description="Associated contact, if any.")
    external_id: str | None = Field(
        description="Provider-side conversation identifier."
    )
    title: str | None = Field(description="Conversation title.")
    status: ConversationStatus = Field(description="Conversation status.")
    metadata: dict[str, Any] = Field(description="Key/value metadata.")
    last_message_at: datetime | None = Field(
        description="Timestamp of the last message in the conversation."
    )
    is_active: bool = Field(description="Whether the conversation is active.")
    created_at: datetime = Field(description="Creation timestamp.")
    updated_at: datetime = Field(description="Last update timestamp.")


class WhatsAppMessageCreate(BaseModel):
    """Payload for creating a WhatsApp message."""

    conversation_id: uuid.UUID = Field(
        description="Conversation the message belongs to."
    )
    external_id: str | None = Field(
        default=None,
        max_length=255,
        description="Provider-side message identifier.",
        json_schema_extra={"examples": ["wamid.1234567890"]},
    )
    direction: MessageDirection = Field(description="Inbound or outbound message.")
    message_type: str = Field(
        default="text",
        min_length=1,
        max_length=32,
        description="Message content type (text, image, video, etc.).",
        json_schema_extra={"examples": ["text"]},
    )
    content: str | None = Field(
        default=None,
        max_length=65535,
        description="Message body for text messages.",
        json_schema_extra={"examples": ["Hello! How can I help?"]},
    )
    media_url: str | None = Field(
        default=None, max_length=2048, description="Media URL for non-text messages."
    )
    status: MessageStatus = Field(
        default=MessageStatus.PENDING, description="Message status."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Optional key/value metadata."
    )
    sent_at: datetime | None = None


class WhatsAppMessageUpdate(BaseModel):
    """Payload for updating a WhatsApp message."""

    external_id: str | None = Field(default=None, max_length=255)
    direction: MessageDirection | None = None
    message_type: str | None = Field(default=None, min_length=1, max_length=32)
    content: str | None = Field(default=None, max_length=65535)
    media_url: str | None = Field(default=None, max_length=2048)
    status: MessageStatus | None = None
    metadata: dict[str, Any] | None = None
    sent_at: datetime | None = None


class WhatsAppMessageResponse(BaseModel):
    """WhatsApp message data returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Message identifier.")
    company_id: uuid.UUID = Field(description="Owning company identifier.")
    integration_id: uuid.UUID = Field(description="Integration identifier.")
    conversation_id: uuid.UUID = Field(description="Conversation identifier.")
    external_id: str | None = Field(description="Provider-side message identifier.")
    direction: MessageDirection = Field(description="Inbound or outbound message.")
    message_type: str = Field(description="Message content type.")
    content: str | None = Field(description="Message body, if any.")
    media_url: str | None = Field(description="Media URL, if any.")
    status: MessageStatus = Field(description="Message status.")
    metadata: dict[str, Any] = Field(description="Key/value metadata.")
    sent_at: datetime | None = Field(description="Timestamp when the message was sent.")
    is_active: bool = Field(description="Whether the message is active.")
    created_at: datetime = Field(description="Creation timestamp.")
    updated_at: datetime = Field(description="Last update timestamp.")


# Kept as type aliases so consumers can use the canonical values without
# importing implementation-specific table classes.
ConversationStatusValue = Literal["open", "pending", "closed"]
MessageStatusValue = Literal["pending", "sent", "delivered", "read", "failed"]
