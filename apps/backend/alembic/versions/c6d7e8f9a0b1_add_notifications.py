"""add notifications table

Revision ID: c6d7e8f9a0b1
Revises: a1b2c3d4e5f7
Create Date: 2026-08-03 17:30:00.000000

Persisted in-app notifications power the dashboard bell. Rows are created
when inbound WhatsApp messages arrive, deduplicated per conversation.

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c6d7e8f9a0b1'
down_revision: str | Sequence[str] | None = 'a1b2c3d4e5f7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.String(length=2048), nullable=True),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("integration_id", sa.Uuid(), nullable=True),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["whatsapp_conversations.id"]
        ),
        sa.ForeignKeyConstraint(
            ["integration_id"], ["whatsapp_integrations.id"]
        ),
        sa.ForeignKeyConstraint(["message_id"], ["whatsapp_messages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notifications_company_id"),
        "notifications",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_type"),
        "notifications",
        ["type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_conversation_id"),
        "notifications",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_integration_id"),
        "notifications",
        ["integration_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_is_read"),
        "notifications",
        ["is_read"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_created_at"),
        "notifications",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_notifications_created_at"), table_name="notifications"
    )
    op.drop_index(
        op.f("ix_notifications_is_read"), table_name="notifications"
    )
    op.drop_index(
        op.f("ix_notifications_integration_id"), table_name="notifications"
    )
    op.drop_index(
        op.f("ix_notifications_conversation_id"), table_name="notifications"
    )
    op.drop_index(op.f("ix_notifications_type"), table_name="notifications")
    op.drop_index(
        op.f("ix_notifications_company_id"), table_name="notifications"
    )
    op.drop_table("notifications")
