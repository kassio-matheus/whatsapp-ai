"""add companies timezone column

Revision ID: d3e4f5a607b8
Revises: c6d7e8f9a0b1
Create Date: 2026-08-06 10:00:00.000000

Adds the ``timezone`` column to ``companies`` so each company can define the
IANA timezone used to display ``created_at`` / ``updated_at`` timestamps across
all modules.

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd3e4f5a6b7c8'
down_revision: str | Sequence[str] | None = 'c6d7e8f9a0b1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "companies",
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default="UTC",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("companies", "timezone")