"""add table document-chunk

Revision ID: 431b1b760333
Revises: b0d89d672b0f
Create Date: 2025-12-08 16:16:22.921547

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '431b1b760333'
down_revision: Union[str, Sequence[str], None] = 'b0d89d672b0f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create document_chunks table
    op.create_table('document_chunks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('cluster_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_document_chunks_id'), 'document_chunks', ['id'], unique=False)
    
    # Drop tables in correct order (child tables first)
    # 1. Drop test_answers first (it depends on test_results and mcqs)
    op.drop_index(op.f('ix_test_answers_id'), table_name='test_answers')
    op.drop_table('test_answers')
    
    # 2. Drop test_results (now safe, no dependencies)
    op.drop_index(op.f('ix_test_results_id'), table_name='test_results')
    op.drop_table('test_results')
    
    # 3. Drop mcqs (now safe)
    op.drop_index(op.f('ix_mcqs_id'), table_name='mcqs')
    op.drop_table('mcqs')
    
    # Add status column to documents
    op.add_column('documents', sa.Column('status', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove status column
    op.drop_column('documents', 'status')
    
    # Recreate tables in correct order (parent tables first)
    # 1. Create mcqs first (parent)
    op.create_table('mcqs',
        sa.Column('id', sa.INTEGER(), server_default=sa.text("nextval('mcqs_id_seq'::regclass)"), autoincrement=True, nullable=False),
        sa.Column('document_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('question', sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column('choices', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=False),
        sa.Column('correct_answer', sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column('explanation', sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column('difficulty', sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column('topic', sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name='mcqs_document_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='mcqs_pkey'),
        postgresql_ignore_search_path=False
    )
    op.create_index(op.f('ix_mcqs_id'), 'mcqs', ['id'], unique=False)
    
    # 2. Create test_results (parent)
    op.create_table('test_results',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('title', sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column('total_questions', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('correct_answers', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('score', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=False),
        sa.Column('completed_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('test_results_user_id_fkey')),
        sa.PrimaryKeyConstraint('id', name=op.f('test_results_pkey'))
    )
    op.create_index(op.f('ix_test_results_id'), 'test_results', ['id'], unique=False)
    
    # 3. Create test_answers (child, depends on both)
    op.create_table('test_answers',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('test_result_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('mcq_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('user_answer', sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column('is_correct', sa.BOOLEAN(), autoincrement=False, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['mcq_id'], ['mcqs.id'], name=op.f('test_answers_mcq_id_fkey')),
        sa.ForeignKeyConstraint(['test_result_id'], ['test_results.id'], name=op.f('test_answers_test_result_id_fkey')),
        sa.PrimaryKeyConstraint('id', name=op.f('test_answers_pkey'))
    )
    op.create_index(op.f('ix_test_answers_id'), 'test_answers', ['id'], unique=False)
    
    # Drop document_chunks
    op.drop_index(op.f('ix_document_chunks_id'), table_name='document_chunks')
    op.drop_table('document_chunks')