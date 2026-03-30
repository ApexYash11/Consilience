#!/usr/bin/env python
"""
Apply migration directly using SQLAlchemy without Alembic.
This bypasses potential Alembic connection issues.
"""

import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

# Load environment variables from .env file if it exists
from dotenv import load_dotenv
load_dotenv()

# Also check common .env locations
for env_file in ['.env', '.env.local', '.env.development']:
    if Path(env_file).exists():
        print(f"Loading environment from {env_file}")
        load_dotenv(env_file)

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


async def apply_migration():
    """Apply the migration to add heartbeat and failure_reason columns."""
    
    # Get database URL
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print('✗ DATABASE_URL not set')
        print(f"Available env vars: {', '.join([k for k in os.environ.keys() if 'DATABASE' in k or 'DB' in k])}")
        return False
    
    # Redact credentials from logs using proper URL parsing
    try:
        parsed = urlparse(db_url)
        if parsed.username or parsed.password:
            # Rebuild URL with masked credentials
            netloc = f"***:***@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            redacted_url = f"{parsed.scheme}://{netloc}{parsed.path}"
            if parsed.query:
                redacted_url += f"?{parsed.query}"
        else:
            # No credentials to redact
            redacted_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}" if parsed.netloc else db_url[:50]
    except Exception:
        # Fallback if URL parsing fails - still sanitize credentials
        # Remove userinfo (username:password@) from the URL before truncating
        sanitized = db_url
        if '@' in db_url:
            # Remove everything before and including the @
            parts = db_url.rsplit('@', 1)  # Split from right to avoid @ in passwords
            if len(parts) == 2:
                scheme_part = parts[0].split('://')
                if len(scheme_part) >= 2:
                    sanitized = scheme_part[0] + '://<redacted>@' + parts[1]
        redacted_url = sanitized[:50] if len(sanitized) > 50 else sanitized
    print(f"Connecting to database: {redacted_url}...")
    
    engine = None
    try:
        # Create async engine
        engine = create_async_engine(
            db_url,
            echo=False,
            pool_pre_ping=True,
            connect_args={"timeout": 10}
        )
        
        async with engine.begin() as conn:
            # Check if columns already exist
            check_sql = text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'research_tasks' 
                    AND column_name = 'last_heartbeat'
                )
            """)
            
            result = await conn.execute(check_sql)
            has_heartbeat = result.scalar()
            
            if has_heartbeat:
                print("✓ Columns already exist - migration appears to be applied")
                return True
            
            print("Applying migration...")
            
            # Add last_heartbeat column
            print("  Adding last_heartbeat column...")
            await conn.execute(text("""
                ALTER TABLE research_tasks
                ADD COLUMN IF NOT EXISTS last_heartbeat TIMESTAMP(6) WITH TIME ZONE
            """))
            
            # Add failure_reason column  
            print("  Adding failure_reason column...")
            await conn.execute(text("""
                ALTER TABLE research_tasks
                ADD COLUMN IF NOT EXISTS failure_reason TEXT
            """))
            
            # Create index on last_heartbeat
            print("  Creating index on last_heartbeat...")
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_research_tasks_last_heartbeat 
                ON research_tasks(last_heartbeat)
            """))
            
            print("✓ Migration applied successfully!")
            return True
            
    except asyncio.TimeoutError:
        print("✗ Connection timeout")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if engine:
            await engine.dispose()


if __name__ == '__main__':
    success = asyncio.run(apply_migration())
    sys.exit(0 if success else 1)
