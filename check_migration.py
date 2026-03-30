#!/usr/bin/env python
"""Check if migration columns exist in the database."""

import os
import sys
from sqlalchemy import inspect, create_engine, text

def check_migration():
    """Check if last_heartbeat and failure_reason columns exist."""
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print('✗ DATABASE_URL not set')
        return False
    
    # Convert async URL to sync URL
    if 'postgresql+asyncpg://' in db_url:
        db_url = db_url.replace('postgresql+asyncpg://', 'postgresql://')
    
    try:
        # Create sync engine with timeout
        engine = create_engine(db_url, connect_args={'connect_timeout': 10})
        
        # Get inspector
        inspector = inspect(engine)
        columns = {col['name']: col for col in inspector.get_columns('research_tasks')}
        
        # Check for new columns
        has_heartbeat = 'last_heartbeat' in columns
        has_reason = 'failure_reason' in columns
        
        print(f"Database schema check:")
        print(f"  last_heartbeat column: {'✓ EXISTS' if has_heartbeat else '✗ MISSING'}")
        print(f"  failure_reason column: {'✓ EXISTS' if has_reason else '✗ MISSING'}")
        
        if has_heartbeat and has_reason:
            print("\n✓ Migration appears to be applied successfully!")
            return True
        else:
            print("\n✗ Migration columns not found")
            return False
            
    except Exception as e:
        print(f'✗ Error checking database: {e}')
        return False

if __name__ == '__main__':
    success = check_migration()
    sys.exit(0 if success else 1)
