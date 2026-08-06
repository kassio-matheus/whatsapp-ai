import uuid
from datetime import datetime

from pydantic import EmailStr, Field
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel


class CompanyBase(SQLModel):
    name: str = SQLField(max_length=255)
    timezone: str = SQLField(default="UTC", max_length=64)
    created_at: datetime = SQLField(default_factory=datetime.now)
    updated_at: datetime = SQLField(default_factory=datetime.now, nullable=True)
    is_active: bool = SQLField(default=True)


class Company(CompanyBase, table=True):
    id: uuid.UUID = SQLField(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = SQLField(foreign_key="users.id", nullable=False, index=True)
    __tablename__ = "companies"


class CompanyCreate(SQLModel):
    """Payload for creating a new company."""

    name: str = Field(
        min_length=1,
        max_length=255,
        description="Company name.",
        json_schema_extra={"examples": ["Acme Inc."]},
    )
    timezone: str | None = Field(
        default=None,
        max_length=64,
        description=(
            "IANA timezone used to display this company's timestamps, "
            "e.g. `America/Sao_Paulo` or `UTC`."
        ),
        json_schema_extra={"examples": ["America/Sao_Paulo"]},
    )


class CompanyUpdate(SQLModel):
    """Payload for updating an existing company."""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="New company name.",
        json_schema_extra={"examples": ["Acme Corporation"]},
    )
    timezone: str | None = Field(
        default=None,
        max_length=64,
        description="IANA timezone used to display this company's timestamps.",
        json_schema_extra={"examples": ["America/Sao_Paulo"]},
    )


class CompanyResponse(SQLModel):
    """Company data returned by the API."""

    id: uuid.UUID = Field(description="Unique company identifier.")
    name: str = Field(description="Company name.")
    timezone: str = Field(description="IANA timezone used for this company's timestamps.")
    is_active: bool = Field(description="Whether the company is active.")
    created_at: datetime = Field(description="Creation timestamp.")
    owner_id: uuid.UUID = Field(
        description="User ID of the company owner (super admin)."
    )


class MemberCreate(SQLModel):
    """Payload for adding a member to a company."""

    email: EmailStr = Field(
        description="Member email address.",
        json_schema_extra={"examples": ["member@acme.com"]},
    )
    password: str = Field(
        min_length=6,
        max_length=128,
        description="Member account password. Minimum 6 characters.",
        json_schema_extra={"examples": ["MemberPassw0rd!"]},
    )


class MemberUpdate(SQLModel):
    """Payload for updating a company member."""

    email: EmailStr | None = Field(
        default=None, description="New member email address."
    )
    password: str | None = Field(
        default=None,
        min_length=6,
        max_length=128,
        description="New member password. Minimum 6 characters.",
    )
    is_active: bool | None = Field(
        default=None, description="Whether the member account is active."
    )


class MemberResponse(SQLModel):
    """Member data returned by the API."""

    id: uuid.UUID = Field(description="Unique member identifier.")
    email: EmailStr = Field(description="Member email address.")
    is_active: bool = Field(description="Whether the member account is active.")
    is_verified: bool = Field(description="Whether the member email is verified.")
    is_super_admin: bool = Field(
        description="Always `false` for members. Super admins own companies."
    )
    company_id: uuid.UUID | None = Field(description="Company this member belongs to.")
    created_at: datetime = Field(description="Account creation timestamp.")
