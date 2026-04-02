"""Add resilience schema columns for concurrency, recovery, and quota control.

Revision ID: 7c2d4a1e9f3b
Revises: 1a5c9f2b7e41
Create Date: 2026-04-03 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c2d4a1e9f3b'
down_revision = '1a5c9f2b7e41'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add columns to research_tasks table for concurrency, recovery, and structured errors
    op.add_column('research_tasks', sa.Column('worker_id', sa.String(64), nullable=True))
    op.add_column('research_tasks', sa.Column('deadline_at', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('research_tasks', sa.Column('error_code', sa.String(64), nullable=True))
    op.add_column('research_tasks', sa.Column('error_context_json', sa.JSON(), nullable=True, server_default=sa.text("'{}'::jsonb")))
    op.add_column('research_tasks', sa.Column('row_version', sa.Integer(), nullable=False, server_default='0'))

    # Add columns to users table for deep quota reservation
    op.add_column('users', sa.Column('deep_quota_inflight', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('deep_quota_inflight_updated_at', sa.TIMESTAMP(timezone=True), nullable=True))

    # Create index on worker_id for efficient task ownership lookups (supports task recovery)
    op.create_index('ix_research_tasks_worker_id', 'research_tasks', ['worker_id'])


def downgrade() -> None:
    # Drop index on worker_id
    op.drop_index('ix_research_tasks_worker_id', table_name='research_tasks')

    # Remove columns from users table
    op.drop_column('users', 'deep_quota_inflight_updated_at')
    op.drop_column('users', 'deep_quota_inflight')

    # Remove columns from research_tasks table
    op.drop_column('research_tasks', 'row_version')
    op.drop_column('research_tasks', 'error_context_json')
    op.drop_column('research_tasks', 'error_code')
    op.drop_column('research_tasks', 'deadline_at')
    op.drop_column('research_tasks', 'worker_id')
