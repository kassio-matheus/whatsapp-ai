"""add company LLM settings

Revision ID: d5e4f3a2b1c0
Revises: 0639c2830ea3
Create Date: 2026-08-03 10:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlmodel.sql import sqltypes

from alembic import op

import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'd5e4f3a2b1c0'
down_revision: str | Sequence[str] | None = '0639c2830ea3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'company_llm_settings',
        sa.Column('company_id', sa.Uuid(), nullable=False),
        sa.Column(
            'selected_provider',
            sqltypes.AutoString(length=32),
            nullable=True,
        ),
        sa.Column(
            'deepseek_api_key_enc',
            sqltypes.AutoString(length=1024),
            nullable=True,
        ),
        sa.Column(
            'openai_api_key_enc',
            sqltypes.AutoString(length=1024),
            nullable=True,
        ),
        sa.Column(
            'gemini_api_key_enc',
            sqltypes.AutoString(length=1024),
            nullable=True,
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('company_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('company_llm_settings')
