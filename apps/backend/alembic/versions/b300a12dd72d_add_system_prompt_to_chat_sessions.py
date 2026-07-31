"""add system_prompt to chat_sessions

Revision ID: b300a12dd72d
Revises: 9874bae75773
Create Date: 2026-07-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b300a12dd72d'
down_revision: Union[str, Sequence[str], None] = '9874bae75773'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('chat_sessions', sa.Column('system_prompt', sa.String(length=65535), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('chat_sessions', 'system_prompt')
