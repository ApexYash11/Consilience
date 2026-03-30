#!/usr/bin/env python
"""
Apply migration directly using synchronous SQLAlchemy.
"""

import os
import sys
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text, create_engine

def apply_migration():
    """Apply the migration to add heartbeat and failure_reason columns."""
    
    # Get database URL
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print('✗ DATABASE_URL not set')
        return False
    
    # Convert async URL to sync URL if needed
    if 'postgresql+asyncpg://' in db_url:
        db_url = db_url.replace('postgresql+asyncpg://', 'postgresql://')
    
    print(f"Applying migration...")
    
    try:
        # Create sync engine
        engine = create_engine(db_url, connect_args={"connect_timeout": 10})
        
        with engine.begin() as conn:
            # Check if columns already exist
            check_sql = text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'research_tasks' 
                    AND column_name = 'last_heartbeat'
                )
            """)
            
            result = conn.execute(check_sql)
            has_heartbeat = result.scalar()
            
            if has_heartbeat:
                print("✓ Columns already exist - migration appears applied")
                return True
            
            # Add last_heartbeat column
            print("  Adding last_heartbeat column...")
            conn.execute(text("""
                ALTER TABLE research_tasks
                ADD COLUMN IF NOT EXISTS last_heartbeat TIMESTAMP(6) WITH TIME ZONE
            """))
            
            # Add failure_reason column  
            print("  Adding failure_reason column...")
            conn.execute(text("""
                ALTER TABLE research_tasks
                ADD COLUMN IF NOT EXISTS failure_reason TEXT
            """))
            
            # Create index on last_heartbeat
            print("  Creating index on last_heartbeat...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_research_tasks_last_heartbeat 
                ON research_tasks(last_heartbeat)
            """))
            
            print("\n✓ Migration applied successfully!")
            return True
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = apply_migration()
    sys.exit(0 if success else 1)
