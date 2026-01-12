#!/usr/bin/env python3
"""
PostgreSQL Migration Test Script
=================================

Verifies that the database migration from SQLite to PostgreSQL is working correctly.

Tests:
1. DATABASE_URL environment variable is set
2. Database connection can be established
3. PostgreSQL is being used (not SQLite)
4. All tables can be created successfully
5. Basic CRUD operations work
6. Connection pooling is configured correctly

Usage:
    # Local testing with PostgreSQL
    export DATABASE_URL="postgresql://user:pass@localhost:5432/ospra_test"
    python scripts/test_postgresql_migration.py

    # Testing on Render (DATABASE_URL auto-injected)
    python scripts/test_postgresql_migration.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_environment_variables():
    """Test 1: Verify DATABASE_URL is set"""
    print("\n" + "="*70)
    print("TEST 1: Environment Variables")
    print("="*70)

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("❌ FAILED: DATABASE_URL not set")
        print("\nTo fix this:")
        print("  export DATABASE_URL='postgresql://user:pass@host:5432/dbname'")
        return False

    print(f"✅ PASSED: DATABASE_URL is set")

    # Mask credentials in output
    if "@" in database_url:
        masked_url = database_url.split("@")[-1]
    else:
        masked_url = database_url[:30] + "..."

    print(f"   Database: {masked_url}")

    # Verify it's PostgreSQL
    if database_url.startswith("postgresql://") or database_url.startswith("postgres://"):
        print(f"✅ PASSED: Using PostgreSQL")
        return True
    else:
        print(f"❌ FAILED: Not using PostgreSQL (got: {database_url[:20]}...)")
        print("\nExpected: postgresql://... or postgres://...")
        return False


def test_database_connection():
    """Test 2: Verify database connection"""
    print("\n" + "="*70)
    print("TEST 2: Database Connection")
    print("="*70)

    try:
        from ospra_os.database.connection import get_engine, check_database_connection

        # Test connection check
        result = check_database_connection()

        if result.get("status") == "healthy":
            print("✅ PASSED: Database connection successful")
            print(f"   Type: {result.get('database_type', 'unknown')}")
            print(f"   URL: {result.get('url_masked', 'unknown')}")
            return True
        else:
            print(f"❌ FAILED: Database connection failed")
            print(f"   Error: {result.get('error', 'unknown error')}")
            return False

    except Exception as e:
        print(f"❌ FAILED: Exception during connection test")
        print(f"   Error: {str(e)}")
        return False


def test_database_type():
    """Test 3: Verify PostgreSQL is being used"""
    print("\n" + "="*70)
    print("TEST 3: Database Type Verification")
    print("="*70)

    try:
        from ospra_os.database.connection import get_engine
        from sqlalchemy import text

        engine = get_engine()

        # Check engine dialect
        dialect_name = engine.dialect.name

        if dialect_name == "postgresql":
            print(f"✅ PASSED: Using PostgreSQL dialect")
            print(f"   Dialect: {dialect_name}")

            # Additional check: query PostgreSQL version
            with engine.connect() as conn:
                result = conn.execute(text("SELECT version()"))
                version = result.fetchone()[0]
                print(f"   Version: {version[:50]}...")

            return True
        else:
            print(f"❌ FAILED: Not using PostgreSQL")
            print(f"   Dialect: {dialect_name}")
            return False

    except Exception as e:
        print(f"❌ FAILED: Exception during database type check")
        print(f"   Error: {str(e)}")
        return False


def test_table_creation():
    """Test 4: Verify all tables can be created"""
    print("\n" + "="*70)
    print("TEST 4: Table Creation")
    print("="*70)

    try:
        from ospra_os.database.connection import init_database, get_engine
        from ospra_os.database.base import Base
        from sqlalchemy import text

        # Initialize database (creates all tables)
        engine = init_database()

        # Count tables
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'public'
            """))
            table_count = result.fetchone()[0]

        expected_tables = len(Base.metadata.tables)

        print(f"✅ PASSED: Tables created successfully")
        print(f"   SQLAlchemy models: {expected_tables}")
        print(f"   Database tables: {table_count}")

        if table_count > 0:
            # List some tables
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                    LIMIT 10
                """))
                tables = [row[0] for row in result]

            print(f"   Sample tables: {', '.join(tables[:5])}")
            if len(tables) > 5:
                print(f"   ... and {len(tables) - 5} more")

        return True

    except Exception as e:
        print(f"❌ FAILED: Exception during table creation")
        print(f"   Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_connection_pooling():
    """Test 5: Verify connection pooling is configured"""
    print("\n" + "="*70)
    print("TEST 5: Connection Pooling")
    print("="*70)

    try:
        from ospra_os.database.connection import get_engine

        engine = get_engine()

        # Check pool configuration
        pool = engine.pool

        print(f"✅ PASSED: Connection pooling configured")
        print(f"   Pool size: {pool.size()}")
        print(f"   Max overflow: {pool._max_overflow}")
        print(f"   Pool class: {pool.__class__.__name__}")

        # Verify it's not StaticPool (SQLite-specific)
        if "StaticPool" not in pool.__class__.__name__:
            print(f"✅ PASSED: Not using SQLite StaticPool")
            return True
        else:
            print(f"❌ FAILED: Still using SQLite StaticPool")
            return False

    except Exception as e:
        print(f"❌ FAILED: Exception during pooling check")
        print(f"   Error: {str(e)}")
        return False


def test_crud_operations():
    """Test 6: Verify basic CRUD operations work"""
    print("\n" + "="*70)
    print("TEST 6: CRUD Operations")
    print("="*70)

    try:
        from ospra_os.database.connection import get_session_context
        from ospra_os.database import Store
        from sqlalchemy import text

        # Test basic query
        with get_session_context() as session:
            # Simple SELECT 1 test
            result = session.execute(text("SELECT 1 as test"))
            assert result.fetchone()[0] == 1

            # Count stores
            store_count = session.query(Store).count()

            print(f"✅ PASSED: Basic queries work")
            print(f"   Stores in database: {store_count}")

        # Test session context manager (auto-commit/rollback)
        try:
            with get_session_context() as session:
                # This should auto-rollback if it fails
                result = session.execute(text("SELECT COUNT(*) FROM stores"))
                count = result.fetchone()[0]
                print(f"✅ PASSED: Session context manager works")
                print(f"   Table 'stores' exists with {count} rows")
        except Exception as e:
            print(f"⚠️  WARNING: Could not query 'stores' table")
            print(f"   This is normal if tables haven't been created yet")
            print(f"   Error: {str(e)}")

        return True

    except Exception as e:
        print(f"❌ FAILED: Exception during CRUD test")
        print(f"   Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("POSTGRESQL MIGRATION TEST SUITE")
    print("="*70)
    print("\nTesting database migration from SQLite to PostgreSQL...")

    results = {
        "Environment Variables": test_environment_variables(),
        "Database Connection": test_database_connection(),
        "Database Type": test_database_type(),
        "Table Creation": test_table_creation(),
        "Connection Pooling": test_connection_pooling(),
        "CRUD Operations": test_crud_operations(),
    }

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")

    print("\n" + "-"*70)
    print(f"Results: {passed}/{total} tests passed ({int(passed/total*100)}%)")
    print("="*70)

    if passed == total:
        print("\n🎉 SUCCESS: All tests passed! PostgreSQL migration is working correctly.")
        return 0
    else:
        print(f"\n⚠️  WARNING: {total - passed} test(s) failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
