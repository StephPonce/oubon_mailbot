"""
Database Migration: Add missing columns to stores table
Run this once to fix the schema mismatch.
"""

import sqlite3
import os
from pathlib import Path

def find_db_file():
    """Find the SQLite database file."""
    possible_paths = [
        "ospra_os.db",
        "data/ospra_os.db", 
        "ospra.db",
        "data/ospra.db",
        "database.db",
        "data/database.db",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # Search in common locations
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith(".db"):
                return os.path.join(root, file)
    
    return None

def migrate():
    db_path = find_db_file()
    
    if not db_path:
        print("[ERROR] No database file found!")
        print("   Creating new database with correct schema...")
        
        # Import and create tables
        try:
            from ospra_os.database.multi_store_models import Base
            from sqlalchemy import create_engine
            
            engine = create_engine("sqlite:///ospra_os.db")
            Base.metadata.create_all(engine)
            print("[SUCCESS] Created new database: ospra_os.db")
        except Exception as e:
            print(f"[ERROR] Failed to create database: {e}")
        return
    
    print(f" Found database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check existing columns in stores table
    cursor.execute("PRAGMA table_info(stores)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    print(f"   Existing columns: {existing_columns}")
    
    # Columns that should exist based on the model
    required_columns = {
        "status": "VARCHAR(20) DEFAULT 'active'",
        "niche": "VARCHAR(100)",
        "target_market": "VARCHAR(50)",
        "currency": "VARCHAR(10) DEFAULT 'USD'",
        "total_revenue": "FLOAT DEFAULT 0",
        "total_orders": "INTEGER DEFAULT 0",
        "monthly_revenue": "FLOAT DEFAULT 0",
        "conversion_rate": "FLOAT DEFAULT 0",
        "rank_position": "INTEGER",
        "rank_change": "INTEGER DEFAULT 0",
        "is_active": "BOOLEAN DEFAULT 1",
        "pending_actions_count": "INTEGER DEFAULT 0",
        "last_sync": "DATETIME",
        "sync_error": "TEXT",
    }
    
    # Add missing columns
    for col_name, col_type in required_columns.items():
        if col_name not in existing_columns:
            try:
                sql = f"ALTER TABLE stores ADD COLUMN {col_name} {col_type}"
                cursor.execute(sql)
                print(f"   [SUCCESS] Added column: {col_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e).lower():
                    print(f"   ⏭  Column already exists: {col_name}")
                else:
                    print(f"   [ERROR] Failed to add {col_name}: {e}")
    
    conn.commit()
    conn.close()
    
    print("\n[SUCCESS] Migration complete!")

if __name__ == "__main__":
    migrate()
