#!/usr/bin/env python3
"""
Delete a user from the Ospra database for testing.
Run from the project root directory.
"""

import sqlite3
import os

# Try multiple possible database locations
db_paths = [
    "ospra_os.db",           # Current default database location
    "./ospra_os.db",
    "data/oubon.db",
    "./data/oubon.db",
    "test_database.db",
    "./test_database.db",
]

def find_and_delete_user(email: str):
    for db_path in db_paths:
        if os.path.exists(db_path):
            print(f" Found database: {db_path}")
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check if users table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if not cursor.fetchone():
                print(f"   [WARNING]  No 'users' table in {db_path}")
                conn.close()
                continue
            
            # Find user
            cursor.execute("SELECT id, email, name FROM users WHERE email = ?", (email,))
            user = cursor.fetchone()
            
            if user:
                print(f"   [SUCCESS] Found user: ID={user[0]}, Email={user[1]}, Name={user[2]}")
                
                # Delete user
                cursor.execute("DELETE FROM users WHERE email = ?", (email,))
                conn.commit()
                print(f"     Deleted user: {email}")
                
                # Verify deletion
                cursor.execute("SELECT COUNT(*) FROM users WHERE email = ?", (email,))
                count = cursor.fetchone()[0]
                if count == 0:
                    print(f"   [SUCCESS] Verified: User no longer exists in database")
                else:
                    print(f"   [ERROR] Error: User still exists!")
            else:
                print(f"   [INFO]  No user found with email: {email}")
            
            # Show remaining users
            cursor.execute("SELECT id, email, name, subscription_tier FROM users LIMIT 10")
            users = cursor.fetchall()
            if users:
                print(f"\n   [LIST] Remaining users in {db_path}:")
                for u in users:
                    print(f"      - ID={u[0]}, Email={u[1]}, Name={u[2]}, Tier={u[3]}")
            else:
                print(f"\n   [LIST] No users remaining in database")
            
            conn.close()
            return True
    
    print("[ERROR] No database found!")
    return False

if __name__ == "__main__":
    email = "sponce96@icloud.com"
    print(f"[SEARCH] Looking for user: {email}\n")
    find_and_delete_user(email)
