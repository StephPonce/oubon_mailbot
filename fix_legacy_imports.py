#!/usr/bin/env python3
"""
Automated script to fix all legacy imports from multi_store_models.

This script will:
1. Find all files importing from ospra_os.database.multi_store_models
2. Replace with correct imports from ospra_os.database
3. Save changes to each file
"""

import re
from pathlib import Path

# Project root
project_root = Path(__file__).parent

# Common import replacements
REPLACEMENTS = [
    # Simple model imports
    (r'from ospra_os\.database\.multi_store_models import ([A-Za-z_, ]+)\n',
     r'from ospra_os.database import \1\n'),

    # SessionLocal needs special handling
    (r'from ospra_os\.database\.multi_store_models import (.*?)SessionLocal(.*?)\n',
     lambda m: f'from ospra_os.database import {m.group(1).strip().strip(",")}{m.group(2).strip().strip(",")}\nfrom ospra_os.database.connection import SessionLocal\n'),

    # get_db function
    (r'from ospra_os\.database\.multi_store_models import get_db',
     r'from ospra_os.database import get_db'),

    # get_multi_store_session
    (r'from ospra_os\.database\.multi_store_models import get_multi_store_session',
     r'from ospra_os.database import get_multi_store_session'),
]

def fix_file_imports(file_path: Path) -> bool:
    """Fix legacy imports in a single file. Returns True if changes were made."""
    try:
        content = file_path.read_text()
        original_content = content

        # Apply replacements
        for pattern, replacement in REPLACEMENTS:
            if callable(replacement):
                # For complex replacements (like SessionLocal)
                content = re.sub(pattern, replacement, content)
            else:
                content = re.sub(pattern, replacement, content)

        # Check if changes were made
        if content != original_content:
            file_path.write_text(content)
            return True
        return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    """Main function to process all Python files"""
    files_changed = 0
    files_processed = 0

    print("🔍 Finding files with legacy imports...")

    # Find all Python files in ospra_os directory
    ospra_files = list(project_root.glob("ospra_os/**/*.py"))
    root_files = [f for f in project_root.glob("*.py") if f.name not in ["fix_legacy_imports.py", "backup_databases.py"]]
    all_files = ospra_files + root_files

    print(f"📂 Found {len(all_files)} Python files to check")
    print()

    for file_path in sorted(all_files):
        files_processed += 1

        # Check if file has legacy imports
        content = file_path.read_text()
        if "ospra_os.database.multi_store_models" in content:
            print(f"🔧 Fixing: {file_path.relative_to(project_root)}")
            if fix_file_imports(file_path):
                files_changed += 1
                print(f"   ✅ Fixed")
            else:
                print(f"   ⚠️  No changes made (complex case - needs manual fix)")

    print()
    print("=" * 60)
    print(f"📊 Summary:")
    print(f"   Files processed: {files_processed}")
    print(f"   Files changed: {files_changed}")
    print(f"   Files remaining: Verify with grep")
    print("=" * 60)
    print()
    print("✅ Automated fixes complete!")
    print("⚠️  Some files may require manual fixes for complex import patterns")

if __name__ == "__main__":
    main()
