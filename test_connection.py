#!/usr/bin/env python3
"""
Test script to verify Neon database connection and auth setup.
Run this to diagnose connection issues before starting the API.
"""

import asyncio
import os
import sys
import httpx
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from dotenv import load_dotenv

load_dotenv()


async def test_database_connection():
    """Test Neon PostgreSQL async connection."""
    print("\n🔍 Testing Neon Database Connection...")
    print("-" * 60)
    
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        print("❌ DATABASE_URL not set in .env")
        return False
    
    print(f"✓ DATABASE_URL present (masked for security)")
    
    # Check for asyncpg
    try:
        import asyncpg
        print("✓ asyncpg installed")
    except ImportError:
        print("❌ asyncpg not installed - install with: pip install asyncpg")
        return False
    
    # Parse connection details
    from sqlalchemy.engine import make_url
    try:
        url_obj = make_url(DATABASE_URL)
        host = url_obj.host
        port = url_obj.port or 5432
        user = url_obj.username
        database = url_obj.database
        password_masked = "***" if url_obj.password else "(empty)"
        
        print(f"✓ Connection URL parsed successfully")
        print(f"  - Host: {host}:{port}")
        print(f"  - User: {user}")
        print(f"  - Database: {database}")
        print(f"  - Password: {password_masked}")
    except Exception as e:
        print(f"❌ Failed to parse DATABASE_URL: {e}")
        return False
    
    # Test actual connection
    try:
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=url_obj.password,
            database=database,
            ssl="require",
            timeout=10
        )
        
        # Test a simple query
        version = await conn.fetchval("SELECT version();")
        print(f"✓ Connected successfully!")
        print(f"  PostgreSQL: {version.split(',')[0][:50]}...")
        
        await conn.close()
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print(f"\n  Troubleshooting:")
        print(f"  1. Verify DATABASE_URL is correct in .env")
        print(f"  2. Check Neon console for active pooler connections")
        print(f"  3. Ensure IP whitelist includes your machine")
        return False


async def test_auth_setup():
    """Test Neon Auth JWKS endpoint."""
    print("\n🔍 Testing Neon Auth Setup...")
    print("-" * 60)
    
    AUTH_URL = os.getenv("AUTH_URL")
    JWKS_URL = os.getenv("JWKS_URL")
    
    if not AUTH_URL:
        print("❌ AUTH_URL not set in .env")
        return False
    if not JWKS_URL:
        print("❌ JWKS_URL not set in .env")
        return False
    
    print(f"✓ AUTH_URL: {AUTH_URL[:50]}...")
    print(f"✓ JWKS_URL: {JWKS_URL[:50]}...")
    
    # Test JWKS endpoint
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(JWKS_URL, timeout=10.0)
            
            if response.status_code == 200:
                jwks_data = response.json()
                if "keys" in jwks_data:
                    print(f"✓ JWKS endpoint reachable")
                    print(f"  - Found {len(jwks_data['keys'])} signing keys")
                    return True
                else:
                    print(f"❌ JWKS response missing 'keys' field: {jwks_data}")
                    return False
            else:
                print(f"❌ JWKS endpoint returned {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False
    except Exception as e:
        print(f"❌ Failed to reach JWKS endpoint: {e}")
        print(f"\n  Troubleshooting:")
        print(f"  1. Verify JWKS_URL is correct in .env")
        print(f"  2. Check network connectivity")
        print(f"  3. Neon auth URL should match your endpoint in console")
        return False


async def test_sqlalchemy_async_engine():
    """Test SQLAlchemy async engine initialization."""
    print("\n🔍 Testing SQLAlchemy Async Engine...")
    print("-" * 60)
    
    try:
        from sqlalchemy import text
        from backend.database.connection import async_engine, AsyncSessionLocal
        
        print("✓ Async engine imported successfully")
        
        # Try to get a connection
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            print("✓ AsyncSession works - can execute queries")
        
        print("✓ SQLAlchemy async engine initialized")
        await async_engine.dispose()
        return True
    except Exception as e:
        print(f"❌ SQLAlchemy async engine failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_environment_variables():
    """Verify all required environment variables are set."""
    print("\n🔍 Checking Environment Variables...")
    print("-" * 60)
    
    required_vars = {
        "DATABASE_URL": "Neon PostgreSQL connection string",
        "AUTH_URL": "Neon Auth endpoint",
        "JWKS_URL": "JWT signing keys endpoint",
        "OPENROUTER_API_KEY": "LLM API key",
    }
    
    optional_vars = {
        "LANGCHAIN_TRACING_V2": "LangSmith integration",
        "LANGCHAIN_API_KEY": "LangSmith API key",
        "FRONTEND_URL": "Frontend origin for CORS",
    }
    
    all_good = True
    
    print("Required Variables:")
    for var, desc in required_vars.items():
        value = os.getenv(var)
        if value:
            masked = value[:20] + "..." if len(value) > 20 else value
            print(f"  ✓ {var}: {masked}")
        else:
            print(f"  ❌ {var}: NOT SET - {desc}")
            all_good = False
    
    print("\nOptional Variables:")
    for var, desc in optional_vars.items():
        value = os.getenv(var)
        if value:
            masked = value[:20] + "..." if len(value) > 20 else value
            print(f"  ✓ {var}: {masked}")
        else:
            print(f"  ⚠️  {var}: not set (optional)")
    
    return all_good


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Consilience Database & Auth Health Check")
    print("=" * 60)
    
    results = {}
    
    # Run tests
    results["env_vars"] = await test_environment_variables()
    results["database"] = await test_database_connection()
    results["auth"] = await test_auth_setup()
    results["sqlalchemy"] = await test_sqlalchemy_async_engine()
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n✓ All checks passed! Your setup is ready.")
        print("  Run: uvicorn backend.api.main:app --reload")
        return 0
    else:
        print("\n❌ Some checks failed. See details above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
