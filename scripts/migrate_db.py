#!/usr/bin/env python3
"""
Database Migration Script
=========================
Helps migrate from SQLite to PostgreSQL.

Usage:
    # Check database connection
    python scripts/migrate_db.py check
    
    # Initialize fresh database
    python scripts/migrate_db.py init
    
    # Export SQLite to SQL (for import into PostgreSQL)
    python scripts/migrate_db.py export
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")


def check_connection():
    """Check database connectivity."""
    from ospra_os.database import check_database_connection
    
    print("🔍 Checking database connection...")
    status = check_database_connection()
    
    if status["status"] == "healthy":
        print(f"✅ Database connected!")
        print(f"   Type: {status['database_type']}")
        print(f"   URL: {status['url_masked']}")
    else:
        print(f"❌ Database error: {status.get('error')}")
        sys.exit(1)


def init_database():
    """Initialize database tables."""
    from ospra_os.database import init_database
    
    print("🔧 Initializing database...")
    init_database()
    print("✅ Database initialized!")


def export_sqlite():
    """Export SQLite data to SQL file for PostgreSQL import."""
    import sqlite3
    from datetime import datetime
    
    sqlite_path = os.getenv("DATABASE_URL", "sqlite:///./ospra_os.db")
    
    # Extract actual path
    if sqlite_path.startswith("sqlite:///"):
        sqlite_path = sqlite_path.replace("sqlite:///", "")
    
    if not os.path.exists(sqlite_path):
        print(f"❌ SQLite database not found: {sqlite_path}")
        sys.exit(1)
    
    print(f"📦 Exporting from: {sqlite_path}")
    
    conn = sqlite3.connect(sqlite_path)
    
    # Generate export filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_path = f"data/export_{timestamp}.sql"
    
    with open(export_path, "w") as f:
        for line in conn.iterdump():
            # Convert SQLite-specific syntax to PostgreSQL
            line = line.replace("AUTOINCREMENT", "")
            line = line.replace("INTEGER PRIMARY KEY", "SERIAL PRIMARY KEY")
            f.write(f"{line}\n")
    
    conn.close()
    
    print(f"✅ Exported to: {export_path}")
    print("\n📝 To import into PostgreSQL:")
    print(f"   psql -h <host> -U <user> -d <database> -f {export_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/migrate_db.py [check|init|export]")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "check":
        check_connection()
    elif command == "init":
        init_database()
    elif command == "export":
        export_sqlite()
    else:
        print(f"❌ Unknown command: {command}")
        print("   Available: check, init, export")
        sys.exit(1)


if __name__ == "__main__":
    main()
