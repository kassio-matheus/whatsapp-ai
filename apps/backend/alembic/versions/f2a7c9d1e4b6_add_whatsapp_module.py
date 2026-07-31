"""add provider-agnostic WhatsApp module

Revision ID: f2a7c9d1e4b6
Revises: c8a9b7d6e5f4
Create Date: 2026-07-31 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2a7c9d1e4b6"
down_revision: str | Sequence[str] | None = "c8a9b7d6e5f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_integrations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("integration_type", sa.String(length=16), nullable=False),
        sa.Column("adapter", sa.String(length=128), nullable=False),
        sa.Column("phone_number", sa.String(length=64), nullable=True),
        sa.Column("external_account_id", sa.String(length=255), nullable=True),
        sa.Column("credentials", sa.JSON(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "name",
            name="uq_whatsapp_integrations_company_name",
        ),
    )
    op.create_index(
        "ix_whatsapp_integrations_company_id",
        "whatsapp_integrations",
        ["company_id"],
        unique=False,
    )

    op.create_table(
        "whatsapp_contacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("integration_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("phone_number", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("profile_picture_url", sa.String(length=2048), nullable=True),
        sa.Column("is_blocked", sa.Boolean(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["integration_id"], ["whatsapp_integrations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "integration_id",
            "external_id",
            name="uq_whatsapp_contacts_integration_external_id",
        ),
    )
    op.create_index(
        "ix_whatsapp_contacts_company_id",
        "whatsapp_contacts",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        "ix_whatsapp_contacts_integration_id",
        "whatsapp_contacts",
        ["integration_id"],
        unique=False,
    )

    op.create_table(
        "whatsapp_conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("integration_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["contact_id"], ["whatsapp_contacts.id"]),
        sa.ForeignKeyConstraint(["integration_id"], ["whatsapp_integrations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "integration_id",
            "external_id",
            name="uq_whatsapp_conversations_integration_external_id",
        ),
    )
    op.create_index(
        "ix_whatsapp_conversations_company_id",
        "whatsapp_conversations",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        "ix_whatsapp_conversations_integration_id",
        "whatsapp_conversations",
        ["integration_id"],
        unique=False,
    )
    op.create_index(
        "ix_whatsapp_conversations_contact_id",
        "whatsapp_conversations",
        ["contact_id"],
        unique=False,
    )
    op.create_index(
        "ix_whatsapp_conversations_last_message_at",
        "whatsapp_conversations",
        ["last_message_at"],
        unique=False,
    )

    op.create_table(
        "whatsapp_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("integration_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("message_type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.String(length=65535), nullable=True),
        sa.Column("media_url", sa.String(length=2048), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["whatsapp_conversations.id"]),
        sa.ForeignKeyConstraint(["integration_id"], ["whatsapp_integrations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "integration_id",
            "external_id",
            name="uq_whatsapp_messages_integration_external_id",
        ),
    )
    op.create_index(
        "ix_whatsapp_messages_company_id",
        "whatsapp_messages",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        "ix_whatsapp_messages_integration_id",
        "whatsapp_messages",
        ["integration_id"],
        unique=False,
    )
    op.create_index(
        "ix_whatsapp_messages_conversation_id",
        "whatsapp_messages",
        ["conversation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_whatsapp_messages_conversation_id", table_name="whatsapp_messages"
    )
    op.drop_index("ix_whatsapp_messages_integration_id", table_name="whatsapp_messages")
    op.drop_index("ix_whatsapp_messages_company_id", table_name="whatsapp_messages")
    op.drop_table("whatsapp_messages")
    op.drop_index(
        "ix_whatsapp_conversations_last_message_at",
        table_name="whatsapp_conversations",
    )
    op.drop_index(
        "ix_whatsapp_conversations_contact_id",
        table_name="whatsapp_conversations",
    )
    op.drop_index(
        "ix_whatsapp_conversations_integration_id",
        table_name="whatsapp_conversations",
    )
    op.drop_index(
        "ix_whatsapp_conversations_company_id",
        table_name="whatsapp_conversations",
    )
    op.drop_table("whatsapp_conversations")
    op.drop_index("ix_whatsapp_contacts_integration_id", table_name="whatsapp_contacts")
    op.drop_index("ix_whatsapp_contacts_company_id", table_name="whatsapp_contacts")
    op.drop_table("whatsapp_contacts")
    op.drop_index(
        "ix_whatsapp_integrations_company_id",
        table_name="whatsapp_integrations",
    )
    op.drop_table("whatsapp_integrations")
