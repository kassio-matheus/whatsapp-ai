"""add AI company knowledge and document extraction

Revision ID: f4e5d6a7b8c9
Revises: d3e4f5a6b7c8
Create Date: 2026-08-06 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f4e5d6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'ai_company_profiles',
        sa.Column('company_id', sa.Uuid(), nullable=False),
        sa.Column('company_info', sqlmodel.sql.sqltypes.AutoString(length=16000), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('company_id'),
    )
    op.create_table(
        'ai_company_documents',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('company_id', sa.Uuid(), nullable=False),
        sa.Column('uploader_id', sa.Uuid(), nullable=False),
        sa.Column('filename', sqlmodel.sql.sqltypes.AutoString(length=512), nullable=False),
        sa.Column('filepath', sqlmodel.sql.sqltypes.AutoString(length=1024), nullable=False),
        sa.Column('mime_type', sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('extraction_status', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['uploader_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ai_company_documents_company_id'), 'ai_company_documents', ['company_id'], unique=False)
    op.create_index(op.f('ix_ai_company_documents_extraction_status'), 'ai_company_documents', ['extraction_status'], unique=False)
    op.create_index(op.f('ix_ai_company_documents_uploader_id'), 'ai_company_documents', ['uploader_id'], unique=False)
    op.add_column('chat_files', sa.Column('extraction_status', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False, server_default='pending'))
    op.add_column('chat_files', sa.Column('extracted_text', sa.Text(), nullable=True))
    op.create_index(op.f('ix_chat_files_extraction_status'), 'chat_files', ['extraction_status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_chat_files_extraction_status'), table_name='chat_files')
    op.drop_column('chat_files', 'extracted_text')
    op.drop_column('chat_files', 'extraction_status')
    op.drop_index(op.f('ix_ai_company_documents_uploader_id'), table_name='ai_company_documents')
    op.drop_index(op.f('ix_ai_company_documents_extraction_status'), table_name='ai_company_documents')
    op.drop_index(op.f('ix_ai_company_documents_company_id'), table_name='ai_company_documents')
    op.drop_table('ai_company_documents')
    op.drop_table('ai_company_profiles')