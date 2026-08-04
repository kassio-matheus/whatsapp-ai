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

    # Internal secret used to authenticate requests originated by the AI agent
    # (the MCP tool calls run against this API in-process). It replaces the
    # user JWT: the AI is authorized natively, acting as the user referenced by
    # ``X-AI-Actor``. When left empty it is derived from ``SECRET_KEY`` so the
    # value is stable across restarts and unforgeable from outside.
    AI_INTERNAL_SECRET: str = ""

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
            "SECRET_ACCESS_KEY",
            "SECRET_ACESS_KEY",
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