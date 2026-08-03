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

    ACCESS_TOKEN_EXPIRES_MINUTES: int = 30
    EMAIL_VERIFICATION_EXPIRES_MINUTES: int = 60
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30

    AI_SESSION_TTL_HOURS: int = 24
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024
    MAX_REQUEST_BYTES: int = 12 * 1024 * 1024
    MAX_CHAT_PROMPT_LENGTH: int = 16_000
    MAX_SYSTEM_PROMPT_LENGTH: int = 8_000

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


settings = Settings()