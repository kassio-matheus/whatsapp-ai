import enum
import uuid
from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Field as SQLField
from sqlmodel import Relationship, SQLModel


class LLMProvider(str, enum.Enum):
    """LLM provider identifiers used for per-company AI configuration."""

    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    GEMINI = "gemini"
    GROQ = "groq"


class ReasoningLevel(str, enum.Enum):
    """Unified "thinking power" for the AI across providers."""

    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CompanyLLMSettings(SQLModel, table=True):
    __tablename__ = "company_llm_settings"

    company_id: uuid.UUID = SQLField(
        primary_key=True, foreign_key="companies.id")
    selected_provider: str | None = SQLField(default=None, max_length=32)
    deepseek_api_key_enc: str | None = SQLField(default=None, max_length=1024)
    openai_api_key_enc: str | None = SQLField(default=None, max_length=1024)
    gemini_api_key_enc: str | None = SQLField(default=None, max_length=1024)
    groq_api_key_enc: str | None = SQLField(default=None, max_length=1024)
    deepseek_model: str | None = SQLField(default=None, max_length=256)
    openai_model: str | None = SQLField(default=None, max_length=256)
    gemini_model: str | None = SQLField(default=None, max_length=256)
    groq_model: str | None = SQLField(default=None, max_length=256)
    deepseek_reasoning_effort: str | None = SQLField(default=None, max_length=32)
    openai_reasoning_effort: str | None = SQLField(default=None, max_length=32)
    gemini_reasoning_effort: str | None = SQLField(default=None, max_length=32)
    groq_reasoning_effort: str | None = SQLField(default=None, max_length=32)
    deepseek_supports_thinking: bool = SQLField(default=True)
    openai_supports_thinking: bool = SQLField(default=True)
    gemini_supports_thinking: bool = SQLField(default=True)
    groq_supports_thinking: bool = SQLField(default=True)
    created_at: datetime = SQLField(default_factory=datetime.now)
    updated_at: datetime = SQLField(
        default_factory=datetime.now, nullable=True)


class AIGlobalSettings(SQLModel, table=True):
    """Single-row global AI configuration used as the platform default.

    The AI module is global: this row backs the AI Chat and every channel that
    does not have a more specific per-company override.
    """

    __tablename__ = "ai_global_settings"

    id: int = SQLField(primary_key=True, default=1)
    selected_provider: str | None = SQLField(default=None, max_length=32)
    deepseek_api_key_enc: str | None = SQLField(default=None, max_length=1024)
    openai_api_key_enc: str | None = SQLField(default=None, max_length=1024)
    gemini_api_key_enc: str | None = SQLField(default=None, max_length=1024)
    groq_api_key_enc: str | None = SQLField(default=None, max_length=1024)
    deepseek_model: str | None = SQLField(default=None, max_length=256)
    openai_model: str | None = SQLField(default=None, max_length=256)
    gemini_model: str | None = SQLField(default=None, max_length=256)
    groq_model: str | None = SQLField(default=None, max_length=256)
    deepseek_reasoning_effort: str | None = SQLField(default=None, max_length=32)
    openai_reasoning_effort: str | None = SQLField(default=None, max_length=32)
    gemini_reasoning_effort: str | None = SQLField(default=None, max_length=32)
    groq_reasoning_effort: str | None = SQLField(default=None, max_length=32)
    deepseek_supports_thinking: bool = SQLField(default=True)
    openai_supports_thinking: bool = SQLField(default=True)
    gemini_supports_thinking: bool = SQLField(default=True)
    groq_supports_thinking: bool = SQLField(default=True)
    updated_at: datetime = SQLField(
        default_factory=datetime.now, nullable=True)


class LLMProviderConfig(BaseModel):
    """Configuration status of a single LLM provider."""

    configured: bool = Field(
        description="Whether an API key is stored for this provider."
    )
    model: str | None = Field(
        default=None, description="Model identifier used when this provider runs."
    )
    supports_thinking: bool = Field(
        default=True,
        description=(
            "Whether this provider's model supports thinking/reasoning. When "
            "false, no thinking parameters are sent to this provider."
        ),
    )
    reasoning_effort: ReasoningLevel = Field(
        default=ReasoningLevel.MEDIUM,
        description="Thinking power applied when this provider runs.",
    )


class LLMSettingsResponse(BaseModel):
    """LLM settings. API keys are never returned."""

    selected_provider: LLMProvider | None = Field(
        default=None,
        description="Provider tried first in the failover chain, if any.",
    )
    providers: dict[str, LLMProviderConfig] = Field(
        description="Configuration status of every available provider."
    )


class AIGlobalSettingsResponse(LLMSettingsResponse):
    """Global AI configuration returned by the API."""


class CompanyLLMSettingsResponse(LLMSettingsResponse):
    """Per-company LLM settings. API keys are never returned."""

    company_id: uuid.UUID = Field(description="Company identifier.")


class CompanyLLMSettingsUpdate(BaseModel):
    """Payload to update per-company LLM settings."""

    selected_provider: LLMProvider | None = Field(
        default=None,
        description=(
            "Provider used first by the company's AI assistant. "
            "Pass `null` to use the global default order."
        ),
    )
    deepseek_api_key: str | None = Field(
        default=None,
        max_length=1024,
        description="DeepSeek API key to store. Empty string removes it.",
    )
    openai_api_key: str | None = Field(
        default=None,
        max_length=1024,
        description="OpenAI API key to store. Empty string removes it.",
    )
    gemini_api_key: str | None = Field(
        default=None,
        max_length=1024,
        description="Gemini API key to store. Empty string removes it.",
    )
    groq_api_key: str | None = Field(
        default=None,
        max_length=1024,
        description="Groq API key to store. Empty string removes it.",
    )
    deepseek_model: str | None = Field(
        default=None,
        max_length=256,
        description="DeepSeek model id. Empty string restores the default.",
    )
    openai_model: str | None = Field(
        default=None,
        max_length=256,
        description="OpenAI model id. Empty string restores the default.",
    )
    gemini_model: str | None = Field(
        default=None,
        max_length=256,
        description="Gemini model id. Empty string restores the default.",
    )
    groq_model: str | None = Field(
        default=None,
        max_length=256,
        description="Groq model id. Empty string restores the default.",
    )
    deepseek_reasoning_effort: ReasoningLevel | None = Field(
        default=None,
        description="DeepSeek thinking power: `minimal`, `low`, `medium`, `high`.",
    )
    openai_reasoning_effort: ReasoningLevel | None = Field(
        default=None,
        description="OpenAI thinking power: `minimal`, `low`, `medium`, `high`.",
    )
    gemini_reasoning_effort: ReasoningLevel | None = Field(
        default=None,
        description="Gemini thinking power: `minimal`, `low`, `medium`, `high`.",
    )
    groq_reasoning_effort: ReasoningLevel | None = Field(
        default=None,
        description="Groq thinking power: `minimal`, `low`, `medium`, `high`.",
    )
    deepseek_supports_thinking: bool | None = Field(
        default=None,
        description="Whether the DeepSeek model supports thinking/reasoning.",
    )
    openai_supports_thinking: bool | None = Field(
        default=None,
        description="Whether the OpenAI model supports thinking/reasoning.",
    )
    gemini_supports_thinking: bool | None = Field(
        default=None,
        description="Whether the Gemini model supports thinking/reasoning.",
    )
    groq_supports_thinking: bool | None = Field(
        default=None,
        description="Whether the Groq model supports thinking/reasoning.",
    )


class AIGlobalSettingsUpdate(BaseModel):
    """Payload to update the global AI configuration."""

    selected_provider: LLMProvider | None = Field(
        default=None,
        description=(
            "Provider used first by the platform AI. "
            "Pass `null` to use the default order."
        ),
    )
    deepseek_api_key: str | None = Field(
        default=None,
        max_length=1024,
        description="DeepSeek API key to store. Empty string removes it.",
    )
    openai_api_key: str | None = Field(
        default=None,
        max_length=1024,
        description="OpenAI API key to store. Empty string removes it.",
    )
    gemini_api_key: str | None = Field(
        default=None,
        max_length=1024,
        description="Gemini API key to store. Empty string removes it.",
    )
    groq_api_key: str | None = Field(
        default=None,
        max_length=1024,
        description="Groq API key to store. Empty string removes it.",
    )
    deepseek_model: str | None = Field(
        default=None,
        max_length=256,
        description="DeepSeek model id. Empty string restores the default.",
    )
    openai_model: str | None = Field(
        default=None,
        max_length=256,
        description="OpenAI model id. Empty string restores the default.",
    )
    gemini_model: str | None = Field(
        default=None,
        max_length=256,
        description="Gemini model id. Empty string restores the default.",
    )
    groq_model: str | None = Field(
        default=None,
        max_length=256,
        description="Groq model id. Empty string restores the default.",
    )
    deepseek_reasoning_effort: ReasoningLevel | None = Field(
        default=None,
        description="DeepSeek thinking power: `minimal`, `low`, `medium`, `high`.",
    )
    openai_reasoning_effort: ReasoningLevel | None = Field(
        default=None,
        description="OpenAI thinking power: `minimal`, `low`, `medium`, `high`.",
    )
    gemini_reasoning_effort: ReasoningLevel | None = Field(
        default=None,
        description="Gemini thinking power: `minimal`, `low`, `medium`, `high`.",
    )
    groq_reasoning_effort: ReasoningLevel | None = Field(
        default=None,
        description="Groq thinking power: `minimal`, `low`, `medium`, `high`.",
    )
    deepseek_supports_thinking: bool | None = Field(
        default=None,
        description="Whether the DeepSeek model supports thinking/reasoning.",
    )
    openai_supports_thinking: bool | None = Field(
        default=None,
        description="Whether the OpenAI model supports thinking/reasoning.",
    )
    gemini_supports_thinking: bool | None = Field(
        default=None,
        description="Whether the Gemini model supports thinking/reasoning.",
    )
    groq_supports_thinking: bool | None = Field(
        default=None,
        description="Whether the Groq model supports thinking/reasoning.",
    )


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
    user_id: uuid.UUID = SQLField(
        foreign_key="users.id", nullable=False, index=True)
    title: str = SQLField(default="New Chat", min_length=1, max_length=255)
    is_active: bool = SQLField(default=True)
    system_prompt: str | None = SQLField(default=None, max_length=8000)
    context_summary: str | None = SQLField(default=None, max_length=16000)
    created_at: datetime = SQLField(default_factory=datetime.now)
    expires_at: datetime = SQLField(default=None)

    messages: list["Message"] = Relationship(back_populates="session")
    files: list["ChatFile"] = Relationship(back_populates="session")


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
    user_id: uuid.UUID = SQLField(
        foreign_key="users.id", nullable=False, index=True)
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
        json_schema_extra={"examples": [
            "You are a concise, friendly sales coach."]},
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
    expires_at: datetime = Field(
        description="Timestamp when the session expires.")
    message_count: int = Field(
        default=0, description="Number of messages in the session."
    )


class MessageResponse(BaseModel):
    """A single message within a chat session."""

    id: uuid.UUID = Field(description="Message identifier.")
    role: str = Field(
        description="Message author: `user`, `assistant`, or `system`.")
    content: str = Field(description="Message body.")
    created_at: datetime = Field(description="Message creation timestamp.")


class ContextSummaryResponse(BaseModel):
    """AI-generated context summary plus the full message history."""

    session_id: uuid.UUID = Field(description="Session identifier.")
    context_summary: str | None = Field(
        description="AI-generated summary of the conversation, if available."
    )
    messages: list[MessageResponse] = Field(
        description="Full message history.")


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
        json_schema_extra={"examples": [
            "You are a concise, friendly sales coach."]},
    )


class ChatRequest(BaseModel):
    """Prompt to send to the AI within an existing session."""

    prompt: str = Field(
        min_length=1,
        max_length=16000,
        description="User prompt. Conversation history is automatically included.",
        json_schema_extra={"examples": [
            "Summarize the main risks in our pipeline."]},
    )


class ChatResponse(BaseModel):
    """AI response to a prompt."""

    response: str = Field(description="Generated assistant reply.")
    session_id: uuid.UUID = Field(
        description="Session that produced the reply.")
