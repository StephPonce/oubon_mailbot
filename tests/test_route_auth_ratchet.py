"""Security ratchet: no NEW unauthenticated state-changing routes.

The August 2026 audit found 92 routes that could delete Shopify products, create
Meta ad campaigns, place supplier orders, enable autopilot and raise its spend
caps — all anonymously. Gating them is in progress; this test makes sure the
number can only go DOWN.

Reading files does not scale and does not stay done. This walks the LIVE FastAPI
app object, so it sees exactly what is served — including routers that shadow
the legacy @app duplicates in main.py, a real trap here (patching the shadowed
copy once looked like a fix and changed nothing).

When you gate a route: delete its line from
tests/data/unauthenticated_routes_baseline.txt. The test will tell you to.
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE = REPO_ROOT / "tests" / "data" / "unauthenticated_routes_baseline.txt"
AUDITOR = REPO_ROOT / "scripts" / "audit_route_auth.py"


def _load_auditor():
    spec = importlib.util.spec_from_file_location("route_auditor", AUDITOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_baseline() -> set[str]:
    lines = BASELINE.read_text().splitlines()
    return {ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")}


def _current_unauthenticated() -> set[str]:
    logging.disable(logging.CRITICAL)
    try:
        rows = _load_auditor().audit()
    finally:
        logging.disable(logging.NOTSET)
    return {
        f"{r['method']} {r['path']}"
        for r in rows
        if not r["protected"] and r["state_changing"] and not r["allowlisted_public"]
    }


def test_no_new_unauthenticated_write_routes():
    current = _current_unauthenticated()
    baseline = _read_baseline()

    new = sorted(current - baseline)
    assert not new, (
        "New unauthenticated state-changing route(s) detected:\n  "
        + "\n  ".join(new)
        + "\n\nEvery route that changes state must depend on "
        "ospra_os.auth.jwt_auth.get_current_user (the STRICT one — the variant "
        "re-exported by ospra_os.auth returns None and never rejects).\n"
        "If a route is genuinely public, add its prefix to PUBLIC_PREFIXES in "
        "scripts/audit_route_auth.py with a justification."
    )


def test_baseline_has_no_stale_entries():
    """Keeps the debt list honest: once a route is gated, its line must go.

    Without this the baseline silently rots into a list of routes that no longer
    exist, and nobody can tell real remaining debt from noise.
    """
    current = _current_unauthenticated()
    baseline = _read_baseline()

    fixed = sorted(baseline - current)
    assert not fixed, (
        "These routes are now protected (or gone) but are still listed as debt:\n  "
        + "\n  ".join(fixed)
        + f"\n\nDelete those {len(fixed)} line(s) from {BASELINE.relative_to(REPO_ROOT)} "
        "so the remaining count stays truthful."
    )
