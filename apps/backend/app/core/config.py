import hashlib
import hmac

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "API"
    API_V1_PREFIX: str = "/api/v1"
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    ALLOWED_HOSTS: list[str] = [""]
    OPENAI_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    SECRET_KEY: str = Field(min_length=32)
    # Optional dedicated key used to encrypt stored AI provider keys instead of
    # SECRET_KEY. Set the SAME value in every environment that shares the same
    # database (e.g. local dev and the deployed server), otherwise keys saved in
    # one environment become unreadable in the other and look "discarded" on
    # restart/deploy. A base64 32-byte value is expected.
    AI_SETTINGS_ENCRYPTION_KEY: str = ""
    # Legacy secrets (JSON list) still accepted for decryption while the active
    # AI settings key rotates. Each entry is tried after the current key.
    AI_SETTINGS_ENCRYPTION_KEYS: list[str] = []
    SQLALCHEMY_DATABASE_URI: str = Field(min_length=1)

    FRONTEND_HOST: str = "http://localhost:3000"

    EMAILS_ENABLED: bool = False
    EMAILS_FROM_NAME: str = "API"
    EMAILS_FROM_EMAIL: str = "noreply@api.com"
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    ACCESS_TOKEN_EXPIRES_MINUTES: int = 10080
    EMAIL_VERIFICATION_EXPIRES_MINUTES: int = 60
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30

    AI_SESSION_TTL_HOURS: int = 24
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024
    MAX_REQUEST_BYTES: int = 12 * 1024 * 1024
    MAX_CHAT_PROMPT_LENGTH: int = 16_000
    MAX_SYSTEM_PROMPT_LENGTH: int = 8_000

    # How many MCP tool *full schemas* are pre-loaded per request. The request
    # is scored against a BM25 index and only the top matches are sent to the
    # model, keeping the prompt small even with hundreds of routes exposed.
    AI_TOOL_SELECTION_LIMIT: int = 8
    # How many tool lines appear in the compact "available tools" catalog
    # appended to the instructions. It lets the model know what exists without
    # paying for every full JSON schema. Set to 0 to disable the catalog.
    AI_TOOL_CATALOG_LIMIT: int = 100
    # When the model calls a tool by name that was not pre-selected, load its
    # definition on demand and run it. Disabling saves tokens but the model can
    # then only use the pre-selected tools.
    AI_TOOL_ON_DEMAND: bool = True

    # Token-saving budgets (in characters, rough 1 token ~= 4 chars). The AI
    # gateway trims conversation history, the system prompt and the user prompt
    # down to these ceilings before the request leaves the backend. They exist
    # because the small (~8B) models this stack targets have tight context
    # windows and degrade when flooded with irrelevant history.
    AI_CONTEXT_BUDGET_TOKENS: int = 10000
    AI_PROMPT_BUDGET_TOKENS: int = 1200
    # Roomier than default because the assistant also carries the injected
    # knowledge block (company information + uploaded documents) inside the
    # system prompt. The knowledge itself is capped separately by
    # ``app.modules.ai.documents``.
    AI_SYSTEM_BUDGET_TOKENS: int = 3000
    # How many recent turns are kept from the conversation history at most.
    # Kept well above the "last 20 messages" requirement so the model always
    # reads a full recent window; the token budget is what trims old turns.
    AI_MAX_CONTEXT_TURNS: int = 40
    # Reasoning level used when neither the company nor the global settings
    # override it. Lower values cut latency at the cost of some "thinking".
    AI_DEFAULT_REASONING_LEVEL: str = "minimal"
    # Max seconds a single provider call (LLM or in-process MCP tool) may take
    # before the failover chain moves to the next provider. Prevents a slow or
    # hung provider from blocking a reply for minutes (the OpenAI SDK default
    # is 600s). Tune up only if a provider needs longer thinking.
    AI_PROVIDER_TIMEOUT_SECONDS: int = 45
    # Verbose tool-call logging (rich console prints). Disabled by default in
    # production because formatting every tool result adds latency to the tool
    # loop; set to True to debug tool selection/execution.
    AI_DEBUG_LOGGING: bool = False

    # Internal secret used to authenticate requests originated by the AI agent
    # (the MCP tool calls run against this API in-process). It replaces the
    # user JWT: the AI is authorized natively, acting as the user referenced by
    # ``X-AI-Actor``. When left empty it is derived from ``SECRET_KEY`` so the
    # value is stable across restarts and unforgeable from outside.
    AI_INTERNAL_SECRET: str = "4Cib7ZF50ywzSYfKqY2Qj7r5if7juCnqbSDAwikJloc"

    # Cloudflare R2 (S3-compatible) object storage
    R2_BUCKET_NAME: str = ""
    R2_ACCESS_KEY_ID: str = Field(
        default="",
        validation_alias=AliasChoices(
            "R2_ACCESS_KEY_ID",
            "ACCESS_KEY_ID",
            "S3_ACCESS_KEY_ID",
        ),
    )
    R2_SECRET_ACCESS_KEY: str = Field(
        default="",
        validation_alias=AliasChoices(
            "R2_SECRET_ACCESS_KEY",
        ),
    )
    R2_API_ENDPOINT: str = Field(
        default="",
        validation_alias=AliasChoices(
            "R2_API_ENDPOINT",
            "S3_API_ENDPOINT",
            "R2_S3_API_ENDPOINT",
        ),
    )
    R2_PUBLIC_BASE_URL: str = ""
    R2_PUBLIC_URL_PATTERN: str = ""

    @property
    def r2_configured(self) -> bool:
        return bool(
            self.R2_BUCKET_NAME
            and self.R2_ACCESS_KEY_ID
            and self.R2_SECRET_ACCESS_KEY
            and self.R2_API_ENDPOINT
        )

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":

        if self.ENVIRONMENT.lower() == "production":
            if self.SECRET_KEY.strip() in {"", "change-me", "secret"}:
                raise ValueError("SECRET_KEY must be configured in production")
            if "*" in self.ALLOWED_HOSTS:
                raise ValueError(
                    "ALLOWED_HOSTS cannot contain '*' in production")
            if "*" in self.BACKEND_CORS_ORIGINS:
                raise ValueError("CORS cannot allow '*' in production")
            if not self.SQLALCHEMY_DATABASE_URI:
                raise ValueError(
                    "SQLALCHEMY_DATABASE_URI is required in production")
        return self


def ai_request_secret() -> str:
    """Return the unforgeable secret used to tag AI-originated requests.

    Prefers the explicitly configured ``AI_INTERNAL_SECRET``; otherwise derives
    a stable value from ``SECRET_KEY`` so the in-process MCP client and the
    auth dependencies always agree without any configuration.
    """
    if settings.AI_INTERNAL_SECRET:
        return settings.AI_INTERNAL_SECRET
    return hmac.new(
        settings.SECRET_KEY.encode(),
        b"ai-internal-request",
        hashlib.sha256,
    ).hexdigest()


settings = Settings()
