import uuid
from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Field as SQLField
from sqlmodel import Relationship, SQLModel


class ChatResponseStructure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: str = Field(description="Generated response for user.")


class AIPlatform(ABC):
    @abstractmethod
    def generate(
        self,
        prompt: str,
        context: list[dict[str, str]] | None = None,
        system_prompt: str | None = None,
        auth_token: str | None = None,
        allowed_tools: list[str] | None = None,
    ) -> ChatResponseStructure: ...


class ChatSession(SQLModel, table=True):
    __tablename__ = "chat_sessions"

    id: uuid.UUID = SQLField(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = SQLField(foreign_key="users.id", nullable=False, index=True)
    title: str = SQLField(default="New Chat", min_length=1, max_length=255)
    is_active: bool = SQLField(default=True)
    system_prompt: str | None = SQLField(default=None, max_length=8000)
    context_summary: str | None = SQLField(default=None, max_length=16000)
    created_at: datetime = SQLField(default_factory=datetime.now)
    expires_at: datetime = SQLField(default=None)

    messages: list[Message] = Relationship(back_populates="session")
    files: list[ChatFile] = Relationship(back_populates="session")


class Message(SQLModel, table=True):
    __tablename__ = "chat_messages"

    id: uuid.UUID = SQLField(default_factory=uuid.uuid4, primary_key=True)
    session_id: uuid.UUID = SQLField(
        foreign_key="chat_sessions.id", nullable=False, index=True
    )
    role: str = SQLField(max_length=16)
    content: str = SQLField(max_length=65535)
    created_at: datetime = SQLField(default_factory=datetime.now)

    session: ChatSession = Relationship(back_populates="messages")


class ChatFile(SQLModel, table=True):
    __tablename__ = "chat_files"

    id: uuid.UUID = SQLField(default_factory=uuid.uuid4, primary_key=True)
    session_id: uuid.UUID = SQLField(
        foreign_key="chat_sessions.id", nullable=False, index=True
    )
    user_id: uuid.UUID = SQLField(foreign_key="users.id", nullable=False, index=True)
    filename: str = SQLField(max_length=512)
    filepath: str = SQLField(max_length=1024)
    mime_type: str = SQLField(max_length=128)
    size_bytes: int = SQLField(default=0)
    created_at: datetime = SQLField(default_factory=datetime.now)

    session: ChatSession = Relationship(back_populates="files")


class ChatSessionCreate(BaseModel):
    """Payload for starting a new chat session."""

    title: str = Field(
        default="New Chat",
        min_length=1,
        max_length=255,
        description="Human-friendly session title.",
        json_schema_extra={"examples": ["Sales strategy brainstorm"]},
    )
    system_prompt: str | None = Field(
        default=None,
        max_length=8000,
        description="Optional system prompt steering the AI behavior for this session.",
        json_schema_extra={"examples": ["You are a concise, friendly sales coach."]},
    )


class ChatSessionResponse(BaseModel):
    """Chat session metadata. Does not include the message history."""

    id: uuid.UUID = Field(description="Unique session identifier.")
    title: str = Field(description="Session title.")
    system_prompt: str | None = Field(
        default=None, description="Current system prompt, if set."
    )
    is_active: bool = Field(description="Whether the session is still active.")
    created_at: datetime = Field(description="Session creation timestamp.")
    expires_at: datetime = Field(description="Timestamp when the session expires.")
    message_count: int = Field(
        default=0, description="Number of messages in the session."
    )


class MessageResponse(BaseModel):
    """A single message within a chat session."""

    id: uuid.UUID = Field(description="Message identifier.")
    role: str = Field(description="Message author: `user`, `assistant`, or `system`.")
    content: str = Field(description="Message body.")
    created_at: datetime = Field(description="Message creation timestamp.")


class ContextSummaryResponse(BaseModel):
    """AI-generated context summary plus the full message history."""

    session_id: uuid.UUID = Field(description="Session identifier.")
    context_summary: str | None = Field(
        description="AI-generated summary of the conversation, if available."
    )
    messages: list[MessageResponse] = Field(description="Full message history.")


class SystemPromptResponse(BaseModel):
    """Current system prompt of a chat session."""

    session_id: uuid.UUID = Field(description="Session identifier.")
    system_prompt: str | None = Field(
        description="Current system prompt, or `null` when unset."
    )


class SystemPromptUpdate(BaseModel):
    """New system prompt for a chat session."""

    system_prompt: str | None = Field(
        default=None,
        max_length=8000,
        description="System prompt to apply. Pass `null` or empty to clear it.",
        json_schema_extra={"examples": ["You are a concise, friendly sales coach."]},
    )


class ChatRequest(BaseModel):
    """Prompt to send to the AI within an existing session."""

    prompt: str = Field(
        min_length=1,
        max_length=16000,
        description="User prompt. Conversation history is automatically included.",
        json_schema_extra={"examples": ["Summarize the main risks in our pipeline."]},
    )


class ChatResponse(BaseModel):
    """AI response to a prompt."""

    response: str = Field(description="Generated assistant reply.")
    session_id: uuid.UUID = Field(description="Session that produced the reply.")
