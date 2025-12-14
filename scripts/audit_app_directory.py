#!/usr/bin/env python3
"""Audit the app/ directory to understand what needs merging."""

import os
from pathlib import Path
from collections import defaultdict

def audit_app_directory():
    app_dir = Path("app")

    if not app_dir.exists():
        print("❌ No app/ directory found")
        return

    # Categorize files
    categories = {
        "routes": [],
        "models": [],
        "services": [],
        "tasks": [],
        "config": [],
        "utils": [],
        "other": []
    }

    for py_file in app_dir.rglob("*.py"):
        rel_path = py_file.relative_to(app_dir)
        name = py_file.stem

        if "route" in name or "endpoint" in name or "api" in name:
            categories["routes"].append(rel_path)
        elif "model" in name or "schema" in name:
            categories["models"].append(rel_path)
        elif "service" in name or "handler" in name or "client" in name:
            categories["services"].append(rel_path)
        elif "task" in name or "worker" in name or "celery" in name:
            categories["tasks"].append(rel_path)
        elif "config" in name or "setting" in name:
            categories["config"].append(rel_path)
        elif "util" in name or "helper" in name:
            categories["utils"].append(rel_path)
        else:
            categories["other"].append(rel_path)

    print("# app/ Directory Audit\n")

    for category, files in categories.items():
        if files:
            print(f"## {category.title()} ({len(files)} files)")
            for f in sorted(files):
                print(f"  - {f}")
            print()

    # Check for potential conflicts with ospra_os
    print("## Potential Conflicts with ospra_os/\n")

    ospra_dir = Path("ospra_os")
    if ospra_dir.exists():
        app_files = {f.name for f in app_dir.rglob("*.py")}
        ospra_files = {f.name for f in ospra_dir.rglob("*.py")}

        conflicts = app_files & ospra_files
        if conflicts:
            print("Files with same name in both directories:")
            for c in sorted(conflicts):
                print(f"  - {c}")
        else:
            print("No filename conflicts found")

    # Print file sizes
    print("\n## File Details\n")
    for py_file in sorted(app_dir.rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        size = py_file.stat().st_size
        rel_path = py_file.relative_to(app_dir)
        print(f"{rel_path} ({size} bytes)")

if __name__ == "__main__":
    audit_app_directory()
