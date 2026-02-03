"""Initial schema creation

Revision ID: 4745fd629317
Revises: 
Create Date: 2026-02-03 19:48:33.982019

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '4745fd629317'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check table existence for fresh vs existing DB
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # --- Fresh DB Check ---
    # Explicitly handle partial schema states. If both tables are missing,
    # treat as a fresh DB. If exactly one exists, abort to avoid mixed state.
    users_exists = 'users' in tables
    research_tasks_exists = 'research_tasks' in tables

    if not users_exists and not research_tasks_exists:
        # Create Types first
        subscription_tier_enum = postgresql.ENUM(
            'FREE', 'PRO', 'ENTERPRISE', name='subscriptiontier', create_type=False
        )
        # Idempotent enum creation (avoids DuplicateObject on existing type)
        op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'subscriptiontier') THEN
                CREATE TYPE subscriptiontier AS ENUM ('FREE', 'PRO', 'ENTERPRISE');
            END IF;
        END$$;
        """)
        
        subscription_status_enum = sa.Enum('ACTIVE', 'PAST_DUE', 'CANCELED', 'TRIALING', 'INCOMPLETE', name='subscriptionstatus')
        subscription_status_enum.create(conn, checkfirst=True)
        
        research_depth_enum = sa.Enum('STANDARD', 'DEEP', name='researchdepth')
        research_depth_enum.create(conn, checkfirst=True)
        
        task_status_enum = sa.Enum('PENDING', 'RUNNING', 'PAUSED', 'COMPLETED', 'FAILED', 'CANCELLED', name='taskstatus')
        task_status_enum.create(conn, checkfirst=True)

        # Baseline creation for fresh DB
        op.create_table('users',
            sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
            sa.Column('email', sa.String(), nullable=False),
            sa.Column('hashed_password', sa.String(length=255), nullable=False),
            sa.Column('full_name', sa.String(length=200), nullable=True),
            sa.Column('neon_user_id', sa.String(length=255), nullable=True),
            sa.Column('subscription_tier', subscription_tier_enum, nullable=False),
            sa.Column('subscription_status', subscription_status_enum, nullable=False),
            sa.Column('stripe_customer_id', sa.String(length=255), nullable=True),
            sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True),
            sa.Column('monthly_standard_quota', sa.Integer(), nullable=True),
            sa.Column('monthly_deep_quota', sa.Integer(), nullable=True),
            sa.Column('standard_papers_this_month', sa.Integer(), nullable=True),
            sa.Column('deep_papers_this_month', sa.Integer(), nullable=True),
            sa.Column('total_tokens_this_month', sa.Integer(), nullable=True),
            sa.Column('total_cost_this_month', sa.Numeric(precision=10, scale=2), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=True),
            sa.Column('is_verified', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
            sa.Column('last_login', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
        op.create_index(op.f('ix_users_neon_user_id'), 'users', ['neon_user_id'], unique=True)
        op.create_index(op.f('ix_users_stripe_customer_id'), 'users', ['stripe_customer_id'], unique=True)
        op.create_index(op.f('ix_users_stripe_subscription_id'), 'users', ['stripe_subscription_id'], unique=True)

        op.create_table('research_tasks',
            sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
            sa.Column('user_id', sa.UUID(), nullable=False),
            sa.Column('title', sa.String(length=500), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('status', task_status_enum, nullable=False),
            sa.Column('research_depth', research_depth_enum, nullable=False),
            sa.Column('config_json', sa.JSON(), nullable=True),
            sa.Column('estimated_cost_usd', sa.Numeric(precision=10, scale=4), nullable=True),
            sa.Column('actual_cost_usd', sa.Numeric(precision=10, scale=4), nullable=True),
            sa.Column('tokens_used', sa.Integer(), nullable=True),
            sa.Column('output_path', sa.String(length=1000), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('metadata_json', sa.JSON(), nullable=True),
            sa.Column('final_state_json', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_research_tasks_user_id'), 'research_tasks', ['user_id'], unique=False)

        op.create_table('agent_actions',
            sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
            sa.Column('task_id', sa.UUID(), nullable=False),
            sa.Column('agent_id', sa.String(length=100), nullable=True),
            sa.Column('agent_name', sa.String(length=100), nullable=True),
            sa.Column('agent_type', sa.String(length=50), nullable=True),
            sa.Column('action', sa.String(length=100), nullable=True),
            sa.Column('input_data_json', sa.JSON(), nullable=True),
            sa.Column('output_data_json', sa.JSON(), nullable=True),
            sa.Column('tokens_used', sa.Integer(), nullable=True),
            sa.Column('cost_usd', sa.Numeric(precision=10, scale=4), nullable=True),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('error', sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(['task_id'], ['research_tasks.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_agent_actions_task_id'), 'agent_actions', ['task_id'], unique=False)
        
        # New tables (Sources, etc.) will be created by the existing logic below since they are not in `tables`
        # We need to make sure we don't duplicate logic.
        # The logic below iterates and creates them if they don't exist.
        pass
    elif users_exists != research_tasks_exists:
        raise RuntimeError(
            "Partial schema detected: expected both 'users' and 'research_tasks' to exist, "
            "but only one was found. Aborting migration to avoid inconsistent state."
        )
    else:
        # --- Existing DB Logic ---
        # 1. Drop old tables safely (with backup)
        # Drop strictly dependent tables first to avoid FK issues
        for table_name in ['contradictions', 'human_checkpoints', 'usage_logs', 'subscriptions', 'sources']:
            if table_name in tables:
                # Create backup table
                op.execute(f"CREATE TABLE IF NOT EXISTS {table_name}_backup AS SELECT * FROM {table_name}")
                
                # Drop indexes explicitly (helpful for some DBs)
                if table_name == 'subscriptions':
                     op.execute("DROP INDEX IF EXISTS idx_subscriptions_user_id")
                elif table_name == 'sources':
                     op.execute("DROP INDEX IF EXISTS idx_sources_task_id")
                elif table_name == 'usage_logs':
                     op.execute("DROP INDEX IF EXISTS idx_usage_user_id")

                # Drop the table
                op.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")

        # 2. Modify Agent Actions
        # Add columns
        op.add_column('agent_actions', sa.Column('agent_name', sa.String(length=100), nullable=True))
        op.add_column('agent_actions', sa.Column('agent_type', sa.String(length=50), nullable=True))
        op.add_column('agent_actions', sa.Column('action', sa.String(length=100), nullable=True))
        op.add_column('agent_actions', sa.Column('input_data_json', sa.JSON(), nullable=True))
        op.add_column('agent_actions', sa.Column('output_data_json', sa.JSON(), nullable=True))
        op.add_column('agent_actions', sa.Column('tokens_used', sa.Integer(), nullable=True))
        op.add_column('agent_actions', sa.Column('cost_usd', sa.Numeric(precision=10, scale=4), nullable=True))
        op.add_column('agent_actions', sa.Column('started_at', sa.DateTime(), nullable=True))
        op.add_column('agent_actions', sa.Column('completed_at', sa.DateTime(), nullable=True))
        op.add_column('agent_actions', sa.Column('error', sa.Text(), nullable=True))
        
        # ID: Preserve server default
        op.alter_column('agent_actions', 'id',
                   existing_type=sa.UUID(),
                   existing_nullable=False)

        # Task ID: Fix NOT NULL
        # Backup orphaned rows before deletion so data can be recovered if needed.
        # Backups stored in agent_actions_backup (retained for manual recovery by DB admins).
        # Downgrade does not restore these rows.
        op.execute("CREATE TABLE IF NOT EXISTS agent_actions_backup (LIKE agent_actions INCLUDING ALL)")
        op.execute("ALTER TABLE agent_actions_backup ADD COLUMN IF NOT EXISTS backup_timestamp TIMESTAMP DEFAULT now()")
        op.execute("ALTER TABLE agent_actions_backup ADD COLUMN IF NOT EXISTS backup_run_id UUID DEFAULT gen_random_uuid()")
        op.execute("INSERT INTO agent_actions_backup SELECT *, now() as backup_timestamp, gen_random_uuid() as backup_run_id FROM agent_actions WHERE task_id IS NULL")
        # Now safely delete orphaned rows
        op.execute("DELETE FROM agent_actions WHERE task_id IS NULL")
        op.alter_column('agent_actions', 'task_id',
               existing_type=sa.UUID(),
               nullable=False)

        op.alter_column('agent_actions', 'agent_id',
                   existing_type=sa.VARCHAR(length=100),
                   type_=sa.String(length=100),
                   existing_nullable=True)
                   
        op.execute("DROP INDEX IF EXISTS idx_actions_task_id")
        op.create_index(op.f('ix_agent_actions_task_id'), 'agent_actions', ['task_id'], unique=False)
        
        # Drop existing FK constraint if present (names can vary across DBs)
        agent_actions_fks = inspector.get_foreign_keys('agent_actions')
        agent_actions_task_fk = next(
            (fk for fk in agent_actions_fks if fk.get('constrained_columns') == ['task_id']),
            None
        )
        agent_actions_task_fk_name = agent_actions_task_fk.get('name') if agent_actions_task_fk else None
        if isinstance(agent_actions_task_fk_name, str) and agent_actions_task_fk_name:
            op.drop_constraint(agent_actions_task_fk_name, 'agent_actions', type_='foreignkey')
        op.create_foreign_key('fk_agent_actions_task_id', 'agent_actions', 'research_tasks', ['task_id'], ['id'], ondelete='CASCADE')
        
        op.drop_column('agent_actions', 'intent')
        op.drop_column('agent_actions', 'output')
        op.drop_column('agent_actions', 'agent_role')
        op.drop_column('agent_actions', 'reasoning')
        op.drop_column('agent_actions', 'timestamp')
        op.drop_column('agent_actions', 'confidence')
        op.drop_column('agent_actions', 'action_type')

        # 3. Modify Research Tasks
        
        # Description (and NOT NULL backfill)
        op.add_column('research_tasks', sa.Column('description', sa.Text(), nullable=True))
        op.execute("UPDATE research_tasks SET description = '' WHERE description IS NULL")
        op.alter_column('research_tasks', 'description', nullable=False)
        
        # Research Depth (Enum)
        research_depth_enum = sa.Enum('STANDARD', 'DEEP', name='researchdepth')
        research_depth_enum.create(op.get_bind(), checkfirst=True)
        op.add_column('research_tasks', sa.Column('research_depth', research_depth_enum, nullable=True))
        op.execute("UPDATE research_tasks SET research_depth = 'STANDARD'::researchdepth WHERE research_depth IS NULL")
        op.alter_column('research_tasks', 'research_depth', nullable=False)
        
        op.add_column('research_tasks', sa.Column('config_json', sa.JSON(), nullable=True))
        op.add_column('research_tasks', sa.Column('estimated_cost_usd', sa.Numeric(precision=10, scale=4), nullable=True))
        op.add_column('research_tasks', sa.Column('actual_cost_usd', sa.Numeric(precision=10, scale=4), nullable=True))
        op.add_column('research_tasks', sa.Column('tokens_used', sa.Integer(), nullable=True))
        op.add_column('research_tasks', sa.Column('output_path', sa.String(length=1000), nullable=True))
        op.add_column('research_tasks', sa.Column('error_message', sa.Text(), nullable=True))
        op.add_column('research_tasks', sa.Column('metadata_json', sa.JSON(), nullable=True))
        op.add_column('research_tasks', sa.Column('final_state_json', sa.JSON(), nullable=True))
        
        # Preserve ID default
        op.alter_column('research_tasks', 'id',
                   existing_type=sa.UUID(),
                   existing_nullable=False)
                   
        op.alter_column('research_tasks', 'user_id',
                   existing_type=sa.UUID(),
                   nullable=False)
        
        op.alter_column('research_tasks', 'title',
                   existing_type=sa.TEXT(),
                   type_=sa.String(length=500),
                   nullable=False)
                   
        # Status Enum conversion
        task_status_enum = sa.Enum('PENDING', 'RUNNING', 'PAUSED', 'COMPLETED', 'FAILED', 'CANCELLED', name='taskstatus')
        task_status_enum.create(op.get_bind(), checkfirst=True)
        # Cast to taskstatus
        op.execute("ALTER TABLE research_tasks ALTER COLUMN status TYPE taskstatus USING status::taskstatus")
        op.alter_column('research_tasks', 'status', nullable=False)
        
        # Preserve created_at default
        op.alter_column('research_tasks', 'created_at',
                   existing_type=postgresql.TIMESTAMP(),
                   nullable=False)
                   
        op.execute("DROP INDEX IF EXISTS idx_tasks_status")
        op.execute("DROP INDEX IF EXISTS idx_tasks_user_id")
        op.create_index(op.f('ix_research_tasks_user_id'), 'research_tasks', ['user_id'], unique=False)
        
        # Drop existing FK constraint on research_tasks.user_id if present (name may differ)
        research_tasks_fks = inspector.get_foreign_keys('research_tasks')
        research_tasks_user_fk = next(
            (fk for fk in research_tasks_fks if fk.get('constrained_columns') == ['user_id']),
            None
        )
        research_tasks_user_fk_name = research_tasks_user_fk.get('name') if research_tasks_user_fk else None
        if isinstance(research_tasks_user_fk_name, str) and research_tasks_user_fk_name:
            op.drop_constraint(research_tasks_user_fk_name, 'research_tasks', type_='foreignkey')
        op.create_foreign_key('fk_research_tasks_user_id', 'research_tasks', 'users', ['user_id'], ['id'], ondelete='CASCADE')

        op.drop_column('research_tasks', 'duration_seconds')
        op.drop_column('research_tasks', 'actual_cost')
        op.drop_column('research_tasks', 'task_type')
        op.drop_column('research_tasks', 'topic')
        op.drop_column('research_tasks', 'requirements')
        op.drop_column('research_tasks', 'estimated_cost')
        op.drop_column('research_tasks', 'result_data')

        # 4. Modify Users

        op.add_column('users', sa.Column('full_name', sa.String(length=200), nullable=True))
        op.add_column('users', sa.Column('neon_user_id', sa.String(length=255), nullable=True))
        
        # Subscription Status Backfill
        sub_status_enum = sa.Enum('ACTIVE', 'PAST_DUE', 'CANCELED', 'TRIALING', 'INCOMPLETE', name='subscriptionstatus')
        sub_status_enum.create(op.get_bind(), checkfirst=True)
        op.add_column('users', sa.Column('subscription_status', sub_status_enum, nullable=True))
        op.execute("UPDATE users SET subscription_status = 'ACTIVE'::subscriptionstatus WHERE subscription_status IS NULL")
        op.alter_column('users', 'subscription_status', nullable=False)
        
        op.add_column('users', sa.Column('stripe_customer_id', sa.String(length=255), nullable=True))
        op.add_column('users', sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True))
        op.add_column('users', sa.Column('monthly_standard_quota', sa.Integer(), nullable=True))
        op.add_column('users', sa.Column('monthly_deep_quota', sa.Integer(), nullable=True))
        op.add_column('users', sa.Column('standard_papers_this_month', sa.Integer(), nullable=True))
        op.add_column('users', sa.Column('deep_papers_this_month', sa.Integer(), nullable=True))
        op.add_column('users', sa.Column('total_tokens_this_month', sa.Integer(), nullable=True))
        op.add_column('users', sa.Column('total_cost_this_month', sa.Numeric(precision=10, scale=2), nullable=True))
        op.add_column('users', sa.Column('is_verified', sa.Boolean(), nullable=True))
        op.add_column('users', sa.Column('last_login', sa.DateTime(), nullable=True))
        
        # Preserve User Defaults (remove server_default=None arguments)
        op.alter_column('users', 'id',
                   existing_type=sa.UUID(),
                   existing_nullable=False)
                   
        op.alter_column('users', 'hashed_password',
                   existing_type=sa.TEXT(),
                   type_=sa.String(length=255),
                   existing_nullable=False)
        
        # Ensure subscriptiontier enum exists before alteration
        sub_tier_enum = sa.Enum('FREE', 'PRO', 'ENTERPRISE', name='subscriptiontier')
        sub_tier_enum.create(op.get_bind(), checkfirst=True)
        
        op.alter_column('users', 'subscription_tier',
                   existing_type=sa.VARCHAR(length=20),
                   type_=sub_tier_enum,
                   nullable=False,
                   postgresql_using="subscription_tier::subscriptiontier")
                   
        op.alter_column('users', 'is_active',
                   existing_type=sa.BOOLEAN(),
                   existing_nullable=True)
                   
        op.alter_column('users', 'created_at',
                   existing_type=postgresql.TIMESTAMP(),
                   nullable=False)
                   
        op.alter_column('users', 'updated_at',
                   existing_type=postgresql.TIMESTAMP(),
                   existing_nullable=True)
                   
        # Remove any pre-existing unique constraint on users.email if present
        users_uniques = inspector.get_unique_constraints('users')
        users_email_unique = next(
            (uc for uc in users_uniques if uc.get('column_names') == ['email']),
            None
        )
        users_email_unique_name = users_email_unique.get('name') if users_email_unique else None
        if isinstance(users_email_unique_name, str) and users_email_unique_name:
            op.drop_constraint(users_email_unique_name, 'users', type_='unique')
        op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
        op.create_index(op.f('ix_users_neon_user_id'), 'users', ['neon_user_id'], unique=True)
        op.create_index(op.f('ix_users_stripe_customer_id'), 'users', ['stripe_customer_id'], unique=True)
        op.create_index(op.f('ix_users_stripe_subscription_id'), 'users', ['stripe_subscription_id'], unique=True)

    # --- 5. Create Tables (Correct Order) ---
    
    # Sources (FIRST)
    op.create_table('sources',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('task_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('title', sa.TEXT(), autoincrement=False, nullable=False),
    sa.Column('authors', postgresql.ARRAY(sa.TEXT()), autoincrement=False, nullable=True),
    sa.Column('publication', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('year', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('doi', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('url', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('credibility', sa.VARCHAR(length=20), autoincrement=False, nullable=True),
    sa.Column('verified', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['task_id'], ['research_tasks.id'], name='sources_task_id_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name='sources_pkey')
    )
    op.create_index('idx_sources_task_id', 'sources', ['task_id'], unique=False)

    # Contradictions (Depends on Sources)
    op.create_table('contradictions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('task_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('source_a_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('source_b_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('contradiction_type', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('severity', sa.VARCHAR(length=20), autoincrement=False, nullable=True),
    sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('resolved', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['source_a_id'], ['sources.id'], name='contradictions_source_a_id_fkey'),
    sa.ForeignKeyConstraint(['source_b_id'], ['sources.id'], name='contradictions_source_b_id_fkey'),
    sa.ForeignKeyConstraint(['task_id'], ['research_tasks.id'], name='contradictions_task_id_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name='contradictions_pkey')
    )

    # Human Checkpoints
    op.create_table('human_checkpoints',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('task_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('checkpoint_type', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('reason', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('resolved_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.Column('decision', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('human_feedback', sa.TEXT(), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['task_id'], ['research_tasks.id'], name='human_checkpoints_task_id_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name='human_checkpoints_pkey')
    )
    
    # Usage Logs
    op.create_table('usage_logs',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('user_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('task_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('tokens_used', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('cost', sa.NUMERIC(precision=10, scale=4), autoincrement=False, nullable=True),
    sa.Column('model_used', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('timestamp', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['task_id'], ['research_tasks.id'], name='usage_logs_task_id_fkey', ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='usage_logs_user_id_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name='usage_logs_pkey')
    )
    op.create_index('idx_usage_user_id', 'usage_logs', ['user_id'], unique=False)
    
    # Subscriptions
    op.create_table('subscriptions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('user_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('stripe_customer_id', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('stripe_subscription_id', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('status', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('plan_name', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('started_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.Column('cancelled_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.Column('current_period_end', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='subscriptions_user_id_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name='subscriptions_pkey')
    )
    op.create_index('idx_subscriptions_user_id', 'subscriptions', ['user_id'], unique=False)


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    op.drop_index(op.f('ix_users_stripe_subscription_id'), table_name='users')
    op.drop_index(op.f('ix_users_stripe_customer_id'), table_name='users')
    op.drop_index(op.f('ix_users_neon_user_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    # Drop any existing unique constraint on users.email before restoring legacy name
    users_uniques = inspector.get_unique_constraints('users')
    users_email_unique = next(
        (uc for uc in users_uniques if uc.get('column_names') == ['email']),
        None
    )
    users_email_unique_name = users_email_unique.get('name') if users_email_unique else None
    if isinstance(users_email_unique_name, str) and users_email_unique_name:
        op.drop_constraint(users_email_unique_name, 'users', type_='unique')
    op.create_unique_constraint('users_email_key', 'users', ['email'], postgresql_nulls_not_distinct=False)
    op.alter_column('users', 'updated_at',
               existing_type=postgresql.TIMESTAMP(),
               server_default=sa.text('now()'),
               existing_nullable=True)
    op.alter_column('users', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               server_default=sa.text('now()'),
               nullable=True)
    op.alter_column('users', 'is_active',
               existing_type=sa.BOOLEAN(),
               server_default=sa.text('true'),
               existing_nullable=True)
    op.alter_column('users', 'subscription_tier',
               existing_type=sa.Enum('FREE', 'PRO', 'ENTERPRISE', name='subscriptiontier'),
               server_default=sa.text("'free'::character varying"),
               type_=sa.VARCHAR(length=20),
               nullable=True)
    op.alter_column('users', 'hashed_password',
               existing_type=sa.String(length=255),
               type_=sa.TEXT(),
               existing_nullable=False)
    op.alter_column('users', 'id',
               existing_type=sa.UUID(),
               server_default=sa.text('gen_random_uuid()'),
               existing_nullable=False)
    op.drop_column('users', 'last_login')
    op.drop_column('users', 'is_verified')
    op.drop_column('users', 'total_cost_this_month')
    op.drop_column('users', 'total_tokens_this_month')
    op.drop_column('users', 'deep_papers_this_month')
    op.drop_column('users', 'standard_papers_this_month')
    op.drop_column('users', 'monthly_deep_quota')
    op.drop_column('users', 'monthly_standard_quota')
    op.drop_column('users', 'stripe_subscription_id')
    op.drop_column('users', 'stripe_customer_id')
    op.drop_column('users', 'subscription_status')
    op.drop_column('users', 'neon_user_id')
    op.drop_column('users', 'full_name')
    op.add_column('research_tasks', sa.Column('result_data', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True))
    op.add_column('research_tasks', sa.Column('estimated_cost', sa.NUMERIC(precision=10, scale=4), autoincrement=False, nullable=True))
    op.add_column('research_tasks', sa.Column('requirements', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True))
    op.add_column('research_tasks', sa.Column('topic', sa.TEXT(), autoincrement=False, nullable=False))
    op.add_column('research_tasks', sa.Column('task_type', sa.VARCHAR(length=20), autoincrement=False, nullable=True))
    op.add_column('research_tasks', sa.Column('actual_cost', sa.NUMERIC(precision=10, scale=4), autoincrement=False, nullable=True))
    op.add_column('research_tasks', sa.Column('duration_seconds', sa.INTEGER(), autoincrement=False, nullable=True))
    # Drop current FK on research_tasks.user_id (name may vary), then restore legacy name
    research_tasks_fks = inspector.get_foreign_keys('research_tasks')
    research_tasks_user_fk = next(
        (fk for fk in research_tasks_fks if fk.get('constrained_columns') == ['user_id']),
        None
    )
    research_tasks_user_fk_name = research_tasks_user_fk.get('name') if research_tasks_user_fk else None
    if isinstance(research_tasks_user_fk_name, str) and research_tasks_user_fk_name:
        op.drop_constraint(research_tasks_user_fk_name, 'research_tasks', type_='foreignkey')
    op.create_foreign_key('research_tasks_user_id_fkey', 'research_tasks', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.drop_index(op.f('ix_research_tasks_user_id'), table_name='research_tasks')
    op.create_index('idx_tasks_user_id', 'research_tasks', ['user_id'], unique=False)
    op.create_index('idx_tasks_status', 'research_tasks', ['status'], unique=False)
    op.alter_column('research_tasks', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               server_default=sa.text('now()'),
               nullable=True)
    op.alter_column('research_tasks', 'status',
               existing_type=sa.Enum('PENDING', 'RUNNING', 'PAUSED', 'COMPLETED', 'FAILED', 'CANCELLED', name='taskstatus'),
               type_=sa.VARCHAR(length=50),
               nullable=True)
    op.alter_column('research_tasks', 'title',
               existing_type=sa.String(length=500),
               type_=sa.TEXT(),
               nullable=True)
    op.alter_column('research_tasks', 'user_id',
               existing_type=sa.UUID(),
               nullable=True)
    op.alter_column('research_tasks', 'id',
               existing_type=sa.UUID(),
               server_default=sa.text('gen_random_uuid()'),
               existing_nullable=False)
    op.drop_column('research_tasks', 'final_state_json')
    op.drop_column('research_tasks', 'metadata_json')
    op.drop_column('research_tasks', 'error_message')
    op.drop_column('research_tasks', 'output_path')
    op.drop_column('research_tasks', 'tokens_used')
    op.drop_column('research_tasks', 'actual_cost_usd')
    op.drop_column('research_tasks', 'estimated_cost_usd')
    op.drop_column('research_tasks', 'config_json')
    op.drop_column('research_tasks', 'research_depth')
    op.drop_column('research_tasks', 'description')
    op.add_column('agent_actions', sa.Column('action_type', sa.VARCHAR(length=50), autoincrement=False, nullable=True))
    op.add_column('agent_actions', sa.Column('confidence', sa.VARCHAR(length=20), autoincrement=False, nullable=True))
    op.add_column('agent_actions', sa.Column('timestamp', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=True))
    op.add_column('agent_actions', sa.Column('reasoning', sa.TEXT(), autoincrement=False, nullable=True))
    op.add_column('agent_actions', sa.Column('agent_role', sa.VARCHAR(length=50), autoincrement=False, nullable=True))
    op.add_column('agent_actions', sa.Column('output', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True))
    op.add_column('agent_actions', sa.Column('intent', sa.TEXT(), autoincrement=False, nullable=True))
    # Drop current FK on agent_actions.task_id (name may vary), then restore legacy name
    agent_actions_fks = inspector.get_foreign_keys('agent_actions')
    agent_actions_task_fk = next(
        (fk for fk in agent_actions_fks if fk.get('constrained_columns') == ['task_id']),
        None
    )
    agent_actions_task_fk_name = agent_actions_task_fk.get('name') if agent_actions_task_fk else None
    if isinstance(agent_actions_task_fk_name, str) and agent_actions_task_fk_name:
        op.drop_constraint(agent_actions_task_fk_name, 'agent_actions', type_='foreignkey')
    op.create_foreign_key('agent_actions_task_id_fkey', 'agent_actions', 'research_tasks', ['task_id'], ['id'], ondelete='CASCADE')
    op.drop_index(op.f('ix_agent_actions_task_id'), table_name='agent_actions')
    op.create_index('idx_actions_task_id', 'agent_actions', ['task_id'], unique=False)
    op.alter_column('agent_actions', 'agent_id',
               existing_type=sa.String(length=100),
               type_=sa.VARCHAR(length=100),
               existing_nullable=True)
    op.alter_column('agent_actions', 'task_id',
               existing_type=sa.UUID(),
               nullable=True)
    op.alter_column('agent_actions', 'id',
               existing_type=sa.UUID(),
               server_default=sa.text('gen_random_uuid()'),
               existing_nullable=False)
    op.drop_column('agent_actions', 'error')
    op.drop_column('agent_actions', 'completed_at')
    op.drop_column('agent_actions', 'started_at')
    op.drop_column('agent_actions', 'cost_usd')
    op.drop_column('agent_actions', 'tokens_used')
    op.drop_column('agent_actions', 'output_data_json')
    op.drop_column('agent_actions', 'input_data_json')
    op.drop_column('agent_actions', 'action')
    op.drop_column('agent_actions', 'agent_type')
    op.drop_column('agent_actions', 'agent_name')
    op.create_table('contradictions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('task_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('source_a_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('source_b_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('contradiction_type', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('severity', sa.VARCHAR(length=20), autoincrement=False, nullable=True),
    sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('resolved', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['source_a_id'], ['sources.id'], name='contradictions_source_a_id_fkey'),
    sa.ForeignKeyConstraint(['source_b_id'], ['sources.id'], name='contradictions_source_b_id_fkey'),
    sa.ForeignKeyConstraint(['task_id'], ['research_tasks.id'], name='contradictions_task_id_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name='contradictions_pkey')
    )
    op.create_table('human_checkpoints',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('task_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('checkpoint_type', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('reason', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('resolved_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.Column('decision', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('human_feedback', sa.TEXT(), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['task_id'], ['research_tasks.id'], name='human_checkpoints_task_id_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name='human_checkpoints_pkey')
    )
    op.create_table('usage_logs',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('user_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('task_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('tokens_used', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('cost', sa.NUMERIC(precision=10, scale=4), autoincrement=False, nullable=True),
    sa.Column('model_used', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('timestamp', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['task_id'], ['research_tasks.id'], name='usage_logs_task_id_fkey', ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='usage_logs_user_id_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name='usage_logs_pkey')
    )
    op.create_index('idx_usage_user_id', 'usage_logs', ['user_id'], unique=False)
    op.create_table('sources',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('task_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('title', sa.TEXT(), autoincrement=False, nullable=False),
    sa.Column('authors', postgresql.ARRAY(sa.TEXT()), autoincrement=False, nullable=True),
    sa.Column('publication', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('year', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('doi', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('url', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('credibility', sa.VARCHAR(length=20), autoincrement=False, nullable=True),
    sa.Column('verified', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['task_id'], ['research_tasks.id'], name='sources_task_id_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name='sources_pkey')
    )
    op.create_index('idx_sources_task_id', 'sources', ['task_id'], unique=False)
    op.create_table('subscriptions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('user_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('stripe_customer_id', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('stripe_subscription_id', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('status', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('plan_name', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('started_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.Column('cancelled_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.Column('current_period_end', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='subscriptions_user_id_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name='subscriptions_pkey')
    )
    op.create_index('idx_subscriptions_user_id', 'subscriptions', ['user_id'], unique=False)
    # ### end Alembic commands ###
