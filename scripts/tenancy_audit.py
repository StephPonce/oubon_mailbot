#!/usr/bin/env python3
"""
Pass 4 - Tenant isolation audit.

For every SQLAlchemy model in ospra_os/database/, classify it as:
- TENANT_SCOPED: has user_id or owner_id column (tenant data)
- STORE_SCOPED: has store_id column (per-store data)
- SHARED: no user/store FK (shared across tenants - e.g. niches, supplier products)
- AMBIGUOUS: has neither but likely should (red flag)
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_DIR = ROOT / "ospra_os" / "database"

# Heuristic: tables that LEGITIMATELY need no user_id
SHARED_OK = {
    "niches",                    # shared niche definitions
    "niche_snapshots",           # global niche health metrics
    "global_learning_weights",   # platform-wide ML weights
    "ai_usage",                  # may be aggregated/shared (verify)
    "ranking_history",           # global product rankings
    "cached_aliexpress_products", # supplier-side cached data
    "product_search_cache",      # supplier-side search cache
    "enhanced_image_cache",      # cached images by URL hash
    "aggregate_insights",        # federated learning - aggregated
    "background_jobs",           # global job queue
    "whitelabel_partners",       # white-label config (per-partner, not per-user)
    "whitelabel_branding",
    "whitelabel_domains",
    "whitelabel_email_settings",
}

# Models that ARE the user / tenant
USER_TABLES = {"users", "password_reset_tokens"}


def find_tables(file: Path):
    """Parse a python file, find SQLAlchemy model classes."""
    src = file.read_text()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []

    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        # Only look at classes that inherit from something containing 'Base'
        bases = []
        for b in node.bases:
            if isinstance(b, ast.Name):
                bases.append(b.id)
            elif isinstance(b, ast.Attribute):
                bases.append(b.attr)
        if not any("Base" in b for b in bases):
            continue

        tablename = None
        cols = set()
        for stmt in node.body:
            # __tablename__ assignment
            if isinstance(stmt, ast.Assign):
                for tgt in stmt.targets:
                    if isinstance(tgt, ast.Name) and tgt.id == "__tablename__":
                        if isinstance(stmt.value, ast.Constant):
                            tablename = stmt.value.value
                # Column assignments: name = Column(...)
                for tgt in stmt.targets:
                    if isinstance(tgt, ast.Name):
                        if isinstance(stmt.value, ast.Call):
                            cols.add(tgt.id)
            # Annotated: name: Mapped[...] = mapped_column(...) (modern SA)
            elif isinstance(stmt, ast.AnnAssign):
                if isinstance(stmt.target, ast.Name):
                    cols.add(stmt.target.id)

        if tablename:
            out.append({
                "file": file.name,
                "class": node.name,
                "table": tablename,
                "cols": cols,
                "line": node.lineno,
            })
    return out


def classify(model):
    cols = model["cols"]
    table = model["table"]

    has_user = any(c in cols for c in ("user_id", "owner_id", "created_by_id", "tenant_id"))
    has_store = "store_id" in cols
    is_user_table = table in USER_TABLES
    is_shared_ok = table in SHARED_OK

    if is_user_table:
        return "USER_TABLE"
    if has_user and has_store:
        return "TENANT+STORE"
    if has_user:
        return "TENANT_SCOPED"
    if has_store:
        return "STORE_SCOPED"
    if is_shared_ok:
        return "SHARED_OK"
    return "AMBIGUOUS"


def main():
    all_models = []
    for f in sorted(DB_DIR.glob("*.py")):
        if f.name in ("__init__.py", "base.py", "connection.py", "seed_products.py"):
            continue
        all_models.extend(find_tables(f))

    print(f"Found {len(all_models)} SQLAlchemy models\n")

    by_class = {}
    for m in all_models:
        cat = classify(m)
        by_class.setdefault(cat, []).append(m)

    order = ["USER_TABLE", "TENANT+STORE", "TENANT_SCOPED", "STORE_SCOPED", "SHARED_OK", "AMBIGUOUS"]
    for cat in order:
        ms = by_class.get(cat, [])
        if not ms:
            continue
        print(f"\n=== {cat} ({len(ms)}) ===")
        for m in ms:
            print(f"  {m['table']:40s} {m['file']}:{m['line']}  ({m['class']})")

    print("\n" + "=" * 70)
    print("FOCUS: AMBIGUOUS tables — verify each is intentionally shared")
    print("=" * 70)


if __name__ == "__main__":
    main()
