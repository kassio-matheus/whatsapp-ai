"""add global AI settings and LLM model columns

Revision ID: c1b2a3d4e5f6
Revises: d5e4f3a2b1c0
Create Date: 2026-08-03 14:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlmodel.sql import sqltypes

import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c1b2a3d4e5f6'
down_revision: str | Sequence[str] | None = 'd5e4f3a2b1c0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'ai_global_settings',
        sa.Column('id', sa.Integer(), nullable=False),
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
        sa.Column(
            'deepseek_model',
            sqltypes.AutoString(length=256),
            nullable=True,
        ),
        sa.Column(
            'openai_model',
            sqltypes.AutoString(length=256),
            nullable=True,
        ),
        sa.Column(
            'gemini_model',
            sqltypes.AutoString(length=256),
            nullable=True,
        ),
        sa.Column(
            'reasoning_effort',
            sqltypes.AutoString(length=32),
            nullable=True,
        ),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    for column in ('deepseek_model', 'openai_model', 'gemini_model'):
        op.add_column(
            'company_llm_settings',
            sa.Column(
                column,
                sqltypes.AutoString(length=256),
                nullable=True,
            ),
        )
    op.add_column(
        'company_llm_settings',
        sa.Column(
            'reasoning_effort',
            sqltypes.AutoString(length=32),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    for column in ('deepseek_model', 'openai_model', 'gemini_model'):
        op.drop_column('company_llm_settings', column)
    op.drop_column('company_llm_settings', 'reasoning_effort')
    op.drop_table('ai_global_settings')
