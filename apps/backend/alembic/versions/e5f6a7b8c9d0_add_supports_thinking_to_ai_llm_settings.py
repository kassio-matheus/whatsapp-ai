"""add supports_thinking to AI LLM settings

Revision ID: e5f6a7b8c9d0
Revises: c1b2a3d4e5f6
Create Date: 2026-08-03 15:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: str | Sequence[str] | None = 'c1b2a3d4e5f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'ai_global_settings',
        sa.Column(
            'supports_thinking',
            sa.Boolean(),
            nullable=False,
            server_default='1',
        ),
    )
    op.add_column(
        'company_llm_settings',
        sa.Column(
            'supports_thinking',
            sa.Boolean(),
            nullable=False,
            server_default='1',
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('company_llm_settings', 'supports_thinking')
    op.drop_column('ai_global_settings', 'supports_thinking')
