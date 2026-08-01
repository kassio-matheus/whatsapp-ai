"""add WhatsApp AI settings

Revision ID: 0639c2830ea3
Revises: f2a7c9d1e4b6
Create Date: 2026-08-01 12:42:44.859256

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlmodel.sql import sqltypes

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0639c2830ea3'
down_revision: str | Sequence[str] | None = 'f2a7c9d1e4b6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'whatsapp_ai_settings',
        sa.Column('company_id', sa.Uuid(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column(
            'system_prompt',
            sqltypes.AutoString(length=16000),
            nullable=True,
        ),
        sa.Column('trusted_phone_numbers', sa.JSON(), nullable=False),
        sa.Column('allowed_contact_tools', sa.JSON(), nullable=False),
        sa.Column('reply_cooldown_seconds', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('company_id'),
    )
    op.create_table(
        'whatsapp_conversation_ai_settings',
        sa.Column('conversation_id', sa.Uuid(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column(
            'system_prompt',
            sqltypes.AutoString(length=16000),
            nullable=True,
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['conversation_id'], ['whatsapp_conversations.id']
        ),
        sa.PrimaryKeyConstraint('conversation_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('whatsapp_conversation_ai_settings')
    op.drop_table('whatsapp_ai_settings')
