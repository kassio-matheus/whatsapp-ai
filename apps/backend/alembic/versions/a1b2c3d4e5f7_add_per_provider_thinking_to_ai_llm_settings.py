"""add per-provider thinking to AI LLM settings

Revision ID: a1b2c3d4e5f7
Revises: 2db05e05006e
Create Date: 2026-08-03 16:20:00.000000

Thinking support is configured per provider/model instead of globally. The
old single-row ``reasoning_effort`` and ``supports_thinking`` columns are
replaced by per-provider columns, carrying over the previous values.

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f7'
down_revision: str | Sequence[str] | None = '2db05e05006e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROVIDERS = ("deepseek", "openai", "gemini", "groq")

_TABLES = ("ai_global_settings", "company_llm_settings")


def upgrade() -> None:
    """Upgrade schema."""
    for table in _TABLES:
        for provider in _PROVIDERS:
            op.add_column(
                table,
                sa.Column(
                    f"{provider}_supports_thinking",
                    sa.Boolean(),
                    nullable=False,
                    server_default="1",
                ),
            )
            op.add_column(
                table,
                sa.Column(
                    f"{provider}_reasoning_effort",
                    sa.String(length=32),
                    nullable=True,
                ),
            )

        # Carry the previous global values over to every provider column.
        for provider in _PROVIDERS:
            op.execute(
                f"UPDATE {table} "
                f"SET {provider}_supports_thinking = supports_thinking"
            )
            op.execute(
                f"UPDATE {table} "
                f"SET {provider}_reasoning_effort = reasoning_effort"
            )

        op.drop_column(table, "reasoning_effort")
        op.drop_column(table, "supports_thinking")


def downgrade() -> None:
    """Downgrade schema."""
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "supports_thinking",
                sa.Boolean(),
                nullable=False,
                server_default="1",
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "reasoning_effort",
                sa.String(length=32),
                nullable=True,
            ),
        )

        for provider in _PROVIDERS:
            op.execute(
                f"UPDATE {table} "
                f"SET supports_thinking = {provider}_supports_thinking"
            )
            op.execute(
                f"UPDATE {table} "
                f"SET reasoning_effort = {provider}_reasoning_effort"
            )
            op.drop_column(table, f"{provider}_reasoning_effort")
            op.drop_column(table, f"{provider}_supports_thinking")
