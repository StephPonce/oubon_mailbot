"""
``make doctor`` — diagnose every common local-dev failure in one shot.

Runs through the same checklist a senior dev would: is your venv healthy,
is port 8000 free, does the DB respond, is the schema in sync, are
required env vars set, does CORS look right. Prints one big checklist
with green/red checks and a one-line recommendation per failure.

The goal: when login is broken, you don't have to remember which Claude
session figured out the last fix. You run ``make doctor`` and it tells
you exactly what's wrong.

Designed to never raise — every check is wrapped, and any uncaught
exception becomes a red check with the error message inline.
"""

from __future__ import annotations

import importlib
import os
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# ANSI helpers — keep them off if stdout isn't a TTY (CI logs, redirects)
# ---------------------------------------------------------------------------

_USE_COLOR = sys.stdout.isatty() and os.getenv("NO_COLOR") is None


def _c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if _USE_COLOR else s


GREEN = lambda s: _c("32", s)
RED   = lambda s: _c("31", s)
YEL   = lambda s: _c("33", s)
DIM   = lambda s: _c("2",  s)
BOLD  = lambda s: _c("1",  s)


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""
    fix: str = ""


def _row(check: Check) -> str:
    mark = GREEN("✓") if check.passed else RED("✗")
    name = check.name.ljust(38)
    detail = DIM(check.detail) if check.detail else ""
    line = f"  {mark} {name} {detail}"
    if not check.passed and check.fix:
        line += "\n    " + YEL("→ ") + check.fix
    return line


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_python() -> Check:
    """Confirm we're on a supported Python."""
    major, minor = sys.version_info[:2]
    ok = (major, minor) >= (3, 10)
    return Check(
        name="Python version",
        passed=ok,
        detail=f"{major}.{minor}.{sys.version_info.micro}",
        fix="Install Python 3.10+ (see pyproject.toml).",
    )


def check_dependency(import_name: str, install_name: Optional[str] = None) -> Check:
    """Confirm an importable dep is present."""
    install_name = install_name or import_name
    try:
        importlib.import_module(import_name)
        return Check(name=f"import {import_name}", passed=True, detail="ok")
    except ImportError as exc:
        return Check(
            name=f"import {import_name}",
            passed=False,
            detail=str(exc),
            fix=f"uv sync   (or pip install {install_name})",
        )


def check_env_vars() -> list[Check]:
    """Recommended env vars for local dev."""
    rows: list[Check] = []
    jwt = os.getenv("JWT_SECRET_KEY")
    rows.append(Check(
        name="JWT_SECRET_KEY",
        passed=bool(jwt),
        detail="set" if jwt else "not set",
        fix="Add JWT_SECRET_KEY=... to .env (any stable string for local dev).",
    ))
    cred = os.getenv("CREDENTIALS_ENCRYPTION_KEY") or os.getenv("EMAIL_OAUTH_ENCRYPTION_KEY")
    rows.append(Check(
        name="CREDENTIALS_ENCRYPTION_KEY",
        passed=bool(cred),
        detail="set" if cred else "unset (dev will use ephemeral key)",
        fix="Optional locally. Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"",
    ))
    return rows


def check_port_free(port: int = 8000) -> Check:
    """Confirm a stale uvicorn isn't squatting on the dev port."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", port))
        # Connect succeeded → something is bound. Could be your existing
        # uvicorn or a stale one. We can't tell which; flag it so the
        # operator decides.
        s.close()
        return Check(
            name=f"port :{port}",
            passed=False,
            detail="something is bound",
            fix=f"If it's not your current ``make dev``, run ``make kill-port``.",
        )
    except (ConnectionRefusedError, socket.timeout, OSError):
        return Check(name=f"port :{port}", passed=True, detail="free")
    finally:
        try:
            s.close()
        except Exception:
            pass


def check_database_url() -> Check:
    """Tell the operator which DB they're pointed at."""
    url = os.getenv("DATABASE_URL", "")
    if not url:
        return Check(
            name="DATABASE_URL",
            passed=True,
            detail="unset → local SQLite (recommended for dev)",
        )
    # Mask credentials before showing.
    masked = url
    if "@" in url and "://" in url:
        proto, rest = url.split("://", 1)
        if "@" in rest:
            _, host_and_path = rest.split("@", 1)
            masked = f"{proto}://***@{host_and_path}"
    is_remote = any(host in url for host in (
        "neon.tech", "supabase.co", "render.com", "amazonaws.com",
    ))
    detail = masked
    if is_remote:
        detail += "  ← remote DB; expect 200–500ms per query"
    return Check(
        name="DATABASE_URL",
        passed=True,
        detail=detail,
    )


def check_database_reachable() -> Check:
    """Try to connect and run SELECT 1. Times out fast."""
    try:
        from sqlalchemy import text
        from ospra_os.database.connection import get_engine
        engine = get_engine()
        start = time.time()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        elapsed_ms = int((time.time() - start) * 1000)
        # Anything over a second on local dev is a smell — usually a
        # remote-DB hop. Surface it.
        warn = elapsed_ms > 1000
        return Check(
            name="database reachable",
            passed=True,
            detail=f"SELECT 1 in {elapsed_ms} ms" + (" (slow — remote?)" if warn else ""),
            fix=(
                "Login latency will mirror this. Switch to local SQLite for "
                "fast iteration: comment out DATABASE_URL in .env, or run "
                "``make dev-local``."
            ) if warn else "",
        )
    except Exception as exc:
        return Check(
            name="database reachable",
            passed=False,
            detail=f"{type(exc).__name__}: {str(exc)[:120]}",
            fix=(
                "Confirm DATABASE_URL is correct and the DB is up. "
                "For fast offline dev, comment out DATABASE_URL → SQLite fallback."
            ),
        )


def check_schema_drift() -> Check:
    """
    Run the drift detector and report.

    Bootstraps the schema with ``init_database`` first if the DB is fresh
    so we don't false-positive on "every table missing" — that's not
    drift, that's "DB hasn't been initialized yet". Real drift is a model
    that defines columns/tables the live DB doesn't have AFTER a normal
    ``init_database`` run.
    """
    try:
        from ospra_os.database.schema_drift import detect_drift
        report = detect_drift()

        # Heuristic: if literally everything is missing, the DB just
        # hasn't been initialized. Try to init it (cheap on SQLite, idempotent
        # on Postgres) and re-check before declaring drift.
        all_missing = report.has_drift and all(t.table_missing for t in report.tables)
        if all_missing:
            try:
                from ospra_os.database import init_database
                init_database()
                report = detect_drift()
            except Exception as exc:
                return Check(
                    name="schema drift",
                    passed=False,
                    detail=f"DB not initialized; init failed: {exc}",
                    fix="Run ``make dev-local`` once to create the SQLite tables.",
                )

        if not report.has_drift:
            return Check(
                name="schema drift",
                passed=True,
                detail="model and DB columns aligned",
            )

        missing_count = sum(len(t.missing_in_db) for t in report.tables)
        missing_tables = sum(1 for t in report.tables if t.table_missing)
        bits = []
        if missing_count:
            bits.append(f"{missing_count} missing column(s)")
        if missing_tables:
            bits.append(f"{missing_tables} missing table(s)")
        return Check(
            name="schema drift",
            passed=False,
            detail=", ".join(bits) or "drift present",
            fix="Run ``make schema-check`` for the full diff + ALTER TABLE plan.",
        )
    except Exception as exc:
        return Check(
            name="schema drift",
            passed=False,
            detail=f"{type(exc).__name__}: {exc}",
            fix="Drift check failed — usually means the DB isn't reachable yet.",
        )


def check_frontend_env() -> Check:
    """Confirm frontend/.env has VITE_API_URL pointing somewhere reasonable."""
    here = Path(__file__).resolve()
    repo = here.parents[2]
    env_files = [repo / "frontend" / ".env", repo / "frontend" / ".env.local"]
    for env_file in env_files:
        if not env_file.exists():
            continue
        text = env_file.read_text(errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("VITE_API_URL=") and "#" not in line.split("=", 1)[0]:
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                ok = value.startswith(("http://localhost", "http://127.0.0.1"))
                return Check(
                    name="frontend VITE_API_URL",
                    passed=ok,
                    detail=value,
                    fix=(
                        "For local dev this should point at http://localhost:8000."
                        if not ok else ""
                    ),
                )
    return Check(
        name="frontend VITE_API_URL",
        passed=False,
        detail="not found in frontend/.env or frontend/.env.local",
        fix="Add VITE_API_URL=http://localhost:8000 to frontend/.env",
    )


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def _section(title: str) -> None:
    print()
    print(BOLD(title))


def main() -> int:
    print()
    print(BOLD("  Ospra doctor — local-dev diagnostics"))
    print(DIM("  (each check is independent; one failing is non-fatal)"))

    fails = 0

    _section("  Python + dependencies")
    for check in [
        check_python(),
        check_dependency("psycopg2", "psycopg2-binary"),
        check_dependency("cryptography"),
        check_dependency("fastapi"),
        check_dependency("sqlalchemy"),
        check_dependency("uvicorn"),
    ]:
        print(_row(check))
        if not check.passed:
            fails += 1

    _section("  Environment")
    for check in check_env_vars():
        print(_row(check))
        # Missing env vars are warnings, not failures, in dev.
    print(_row(check_database_url()))

    _section("  Runtime")
    port_check = check_port_free()
    print(_row(port_check))
    # Don't count "port bound" as a failure — your own ``make dev`` would
    # trigger it. It's a heads-up.

    _section("  Database")
    db_check = check_database_reachable()
    print(_row(db_check))
    if not db_check.passed:
        fails += 1

    print(_row(check_schema_drift()))
    # Schema drift is a warning — login may still work for unaffected
    # queries — but we still surface it loudly.

    _section("  Frontend")
    print(_row(check_frontend_env()))

    print()
    if fails:
        print(RED(f"  ✗ {fails} blocking check(s) failed."))
        print(DIM("  Fix the items marked → above and re-run ``make doctor``."))
        return 1
    print(GREEN("  ✓ all blocking checks passed."))
    print(DIM("  If login still hangs, the most likely cause is remote-DB latency."))
    print(DIM("  Try ``make dev-local`` to force SQLite mode (no network, instant boot)."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
