#!/usr/bin/env python3
"""Backup all SQLite database files before cleanup"""

import os
import shutil
from datetime import datetime
from pathlib import Path

# Get project root
project_root = Path(__file__).parent

# Create timestamped backup directory
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_dir = project_root / "backups" / timestamp
backup_dir.mkdir(parents=True, exist_ok=True)

# List of database files to backup (from audit)
db_files = [
    "./ospra_os/data/ospra.sqlite",
    "./ospra_os/data/ospra 2.sqlite",
    "./celerybeat-schedule.db",
    "./multi_store.db",
    "./test_database.db",
    "./ospra_os.db",
    "./data/oubon.db",
    "./data/multi_store.db",
    "./data/ospra_local.db",
    "./data/inventory_history.db",
    "./data/mailbot.db",
    "./data/product_history.db",
    "./data/auto_deploy.db",
    "./data/action_history.db",
    "./data/ospra_os.db",
    "./data/oubon_store.db",
    "./oubon_store 3.db",
    "./oubon_store.db",
]

backed_up = 0
skipped = 0

print(f"📦 Backing up database files to: {backup_dir}")
print()

for db_path in db_files:
    full_path = project_root / db_path
    if full_path.exists():
        try:
            # Preserve the relative structure
            dest = backup_dir / full_path.name
            shutil.copy2(full_path, dest)
            print(f"✅ Backed up: {db_path}")
            backed_up += 1
        except Exception as e:
            print(f"❌ Failed to backup {db_path}: {e}")
    else:
        skipped += 1

print()
print(f"📊 Summary:")
print(f"  - Files backed up: {backed_up}")
print(f"  - Files skipped (not found): {skipped}")
print(f"  - Backup location: {backup_dir}")
print()
print("✅ Backup complete!")
