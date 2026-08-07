import uuid
from datetime import datetime

from pydantic import EmailStr, Field
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel


class UserBase(SQLModel):
    email: EmailStr = SQLField(unique=True, index=True, max_length=255)
    created_at: datetime = SQLField(default_factory=datetime.now)
    updated_at: datetime = SQLField(
        default_factory=datetime.now, nullable=True)
    is_active: bool = SQLField(default=True)
    is_verified: bool = SQLField(default=True)
    is_super_admin: bool = SQLField(default=True)
    company_id: uuid.UUID | None = SQLField(
        default=None, foreign_key="companies.id", index=True
    )


class UserRegister(SQLModel):
    """Credentials for creating a new user account."""

    email: EmailStr = Field(
        description="Unique email address used to sign in.",
        json_schema_extra={"examples": ["user@example.com"]},
    )
    password: str = Field(
        min_length=12,
        max_length=128,
        description="Account password. Minimum 12 characters.",
        json_schema_extra={"examples": ["StrongPassw0rd!"]},
    )


class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None)
    password: str | None = Field(default=None, min_length=12, max_length=128)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=12, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class NewPassword(SQLModel):
    """New password and the recovery token issued via `POST /auth/recover-password`."""

    password: str = Field(
        min_length=12,
        max_length=128,
        description="New account password. Minimum 12 characters.",
        json_schema_extra={"examples": ["NewStrongPassw0rd!"]},
    )
    token: str = Field(
        min_length=32,
        max_length=256,
        description="Single-use recovery token from the recovery email.",
        json_schema_extra={"examples": ["recovery-token-value"]},
    )


class LoginRequest(SQLModel):
    """Credentials for authenticating a user."""

    email: EmailStr = Field(
        description="Registered email address.",
        json_schema_extra={"examples": ["user@example.com"]},
    )
    password: str = Field(
        min_length=1,
        max_length=128,
        description="Account password.",
        json_schema_extra={"examples": ["StrongPassw0rd!"]},
    )


class UserData(SQLModel):
    """Public profile of the authenticated user."""

    email: EmailStr = Field(
        description="User email address.",
        json_schema_extra={"examples": ["user@example.com"]},
    )
    is_super_admin: bool = Field(
        description="Whether the user has super admin privileges.",
    )
    company_id: uuid.UUID | None = Field(
        description="Company this user belongs to, if any.",
    )


class Token(SQLModel):
    """JWT access token returned after successful authentication."""

    access_token: str = Field(
        description="JWT bearer token. Send it in the `Authorization` header.",
        json_schema_extra={"examples": ["eyJhbGciOiJIUzI1NiIs..."]},
    )
    token_type: str = Field(
        default="bearer",
        description="Token type. Always `bearer`.",
        json_schema_extra={"examples": ["bearer"]},
    )


class RefreshToken(SQLModel):
    refresh_token: str = Field(description="Refresh token.")
    token_type: str = Field(default="bearer", description="Token type.")


class TokenPayload(SQLModel):
    sub: str = Field(description="Subject of the token (user ID).")


class User(UserBase, table=True):
    id: uuid.UUID = SQLField(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str = SQLField(max_length=128, nullable=False)
    password_reset_token_hash: str | None = SQLField(
        default=None, max_length=64)
    password_reset_token_expires_at: datetime | None = SQLField(default=None)
    __tablename__ = "users"
