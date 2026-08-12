#!/usr/bin/env python
"""Enumerate EVERY registered route and report which ones have no auth.

Why this exists: the August 2026 audit found ~38 unauthenticated routes that
delete Shopify products, create Meta ad campaigns, and place supplier orders.
Finding them by reading files does not scale and does not stay found — a new
route added next month reintroduces the problem silently.

This walks the live FastAPI app object, so it sees exactly what is served,
including routers that SHADOW the legacy @app duplicates in main.py (a real
trap here: patching the shadowed copy changes nothing).

Usage:
    uv run python scripts/audit_route_auth.py           # summary + risky routes
    uv run python scripts/audit_route_auth.py --all     # every route
    uv run python scripts/audit_route_auth.py --json    # machine-readable

A route counts as protected when any dependency in its dependant tree resolves
to a callable whose name looks like an auth gate. NOTE the codebase has TWO
functions named get_current_user and one of them (auth/dependencies.py) returns
None instead of raising — this script reports that variant as UNPROTECTED,
because it is.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

# Import the app quietly — startup is chatty and drowns the report.
logging.disable(logging.CRITICAL)
os.environ.setdefault("DISABLE_STARTUP_JOBS", "1")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Dependencies that actually reject an anonymous caller.
STRICT_AUTH = {
    "get_current_user",
    "require_admin_user",
    "get_current_active_user",
    "require_tier",
    "verify_admin",
    "get_tenant_context",
    # Tenant dependencies ARE auth: tenancy/dependencies.py get_tenant()
    # converts a missing tenant into 401 (it used to leak a 500, which is why
    # these routes look broken rather than gated in probes).
    "get_tenant",
    "get_tenant_db",
    "require_tenant",
}
# Looks like auth, is not: returns None instead of raising.
FAKE_AUTH = {"get_current_user_optional", "get_optional_tenant"}

STATE_CHANGING = {"POST", "PUT", "PATCH", "DELETE"}

# Routes that are legitimately public. Anything else unauthenticated and
# state-changing is a finding. Keep this list SHORT and justified.
PUBLIC_PREFIXES = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/static",
    "/generated_images",
    "/api/auth/",          # login/register/refresh — rate-limited instead
    "/webhooks/",          # HMAC-verified
    "/api/webhooks/",      # HMAC-verified
    "/api/public/",
)


def _dependency_names(route) -> set[str]:
    """Every dependency callable name in the route's tree."""
    names: set[str] = set()
    dependant = getattr(route, "dependant", None)
    if dependant is None:
        return names
    stack = [dependant]
    while stack:
        d = stack.pop()
        call = getattr(d, "call", None)
        if call is not None and getattr(call, "__name__", None):
            names.add(call.__name__)
        stack.extend(getattr(d, "dependencies", []) or [])
    return names


def _has_security_scheme(route) -> bool:
    """True when any dependency declares an HTTP security scheme.

    Name matching alone under-reports: factory-style gates like
    `Depends(require_admin)` or `Depends(require_tier("soar"))` produce inner
    functions whose names are not in any fixed list, which made this script
    report protected routes as open. FastAPI records the scheme on the dependant
    tree, so this catches them regardless of naming.
    """
    dependant = getattr(route, "dependant", None)
    if dependant is None:
        return False
    stack = [dependant]
    while stack:
        d = stack.pop()
        if getattr(d, "security_requirements", None):
            return True
        stack.extend(getattr(d, "dependencies", []) or [])
    return False


def audit() -> list[dict]:
    from ospra_os.main import app

    rows: list[dict] = []
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods:
            continue
        deps = _dependency_names(route)
        strict = sorted(deps & STRICT_AUTH)
        fake = sorted(deps & FAKE_AUTH)
        # Factory-style gates (require_admin, require_tier("soar"), ...) have
        # unpredictable inner names but still declare a security scheme.
        if not strict and _has_security_scheme(route) and not fake:
            strict = ["<security-scheme>"]
        # Catch-all for gates named by convention but absent from STRICT_AUTH.
        if not strict and not fake:
            byname = sorted(
                n for n in deps
                if n.startswith("require_") or n.endswith("_auth")
                or "current_user" in n or "verify_admin" in n
            )
            if byname:
                strict = byname
        for method in sorted(m for m in methods if m not in {"HEAD", "OPTIONS"}):
            public = path.startswith(PUBLIC_PREFIXES)
            rows.append({
                "method": method,
                "path": path,
                "protected": bool(strict),
                "auth_deps": strict,
                "fake_auth": fake,
                "state_changing": method in STATE_CHANGING,
                "allowlisted_public": public,
                "endpoint": getattr(getattr(route, "endpoint", None), "__name__", "?"),
            })
    rows.sort(key=lambda r: (r["path"], r["method"]))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="list every route")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    rows = audit()
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0

    risky = [
        r for r in rows
        if not r["protected"] and r["state_changing"] and not r["allowlisted_public"]
    ]
    fake = [r for r in rows if r["fake_auth"] and not r["protected"]]
    open_reads = [
        r for r in rows
        if not r["protected"] and not r["state_changing"] and not r["allowlisted_public"]
    ]

    print(f"Total routes:                      {len(rows)}")
    print(f"Protected (strict auth dep):       {sum(1 for r in rows if r['protected'])}")
    print(f"Public by allowlist:               {sum(1 for r in rows if r['allowlisted_public'])}")
    print(f"UNAUTH + state-changing (RISK):    {len(risky)}")
    print(f"UNAUTH reads (review):             {len(open_reads)}")
    print(f"Using the NON-REJECTING variant:   {len(fake)}")

    if risky:
        print("\n--- UNAUTHENTICATED STATE-CHANGING ROUTES ---")
        for r in risky:
            print(f"  {r['method']:6} {r['path']:58} {r['endpoint']}")
    if fake:
        print("\n--- FALSE SENSE OF SECURITY (get_current_user_optional) ---")
        for r in fake:
            print(f"  {r['method']:6} {r['path']:58} {r['endpoint']}")

    if args.all:
        print("\n--- ALL ROUTES ---")
        for r in rows:
            flag = "AUTH" if r["protected"] else ("PUB " if r["allowlisted_public"] else "OPEN")
            print(f"  [{flag}] {r['method']:6} {r['path']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
