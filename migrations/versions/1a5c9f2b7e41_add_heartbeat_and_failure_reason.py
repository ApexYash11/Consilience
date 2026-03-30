"""Add heartbeat and failure_reason columns for task recovery

Revision ID: 1a5c9f2b7e41
Revises: 0b4e2f1b4683
Create Date: 2026-03-30 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a5c9f2b7e41'
down_revision: Union[str, None] = '0b4e2f1b4683'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add heartbeat and failure_reason columns to research_tasks table."""
    # Add last_heartbeat column - nullable DateTime with timezone support for offset-naive datetimes
    # Using TIMESTAMP WITHOUT TIME ZONE to match datetime.utcnow() usage (offset-naive)
    op.add_column(
        'research_tasks',
        sa.Column('last_heartbeat', sa.TIMESTAMP, nullable=True, index=True)
    )
    
    # Add failure_reason column - nullable Text for storing why task failed/orphaned
    op.add_column(
        'research_tasks',
        sa.Column('failure_reason', sa.Text, nullable=True)
    )


def downgrade() -> None:
    """Remove heartbeat and failure_reason columns from research_tasks table."""
    op.drop_column('research_tasks', 'failure_reason')
    op.drop_column('research_tasks', 'last_heartbeat')
