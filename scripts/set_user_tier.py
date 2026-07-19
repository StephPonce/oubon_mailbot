"""Operator tool: list users or set a user's subscription tier.

Born from a real support moment: upgrading the owner's account required
pasting multi-line SQL/Python into the Render web shell, which mangles
multi-line pastes (stray backslashes + indentation). This makes it ONE
short argument-driven command with no quoting at all.

Usage (Render shell, or locally with DATABASE_URL set):

    python scripts/set_user_tier.py --list
    python scripts/set_user_tier.py <email> <TIER>

Example:

    python scripts/set_user_tier.py owner@example.com STRATOSPHERE

Notes:
- TIER must be one of the SubscriptionTier enum NAMES (NEST, FLIGHT,
  SOAR, STRATOSPHERE, ...) — validated before touching the DB.
- The tier claim is baked into the JWT at login: the user must log out
  and back in before the new tier applies (rate limits, tier gates).
"""

from __future__ import annotations

import os
import sys

# Runnable as `python scripts/set_user_tier.py` from the repo root: put the
# repo root (not scripts/) on sys.path so `import ospra_os` resolves.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main(argv: list[str]) -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL is not set in this shell.")
        return 2

    from sqlalchemy import create_engine, text

    engine = create_engine(url)

    if len(argv) == 0 or argv[0] == "--list":
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT id, email, subscription_tier FROM users ORDER BY id")
            ).fetchall()
        if not rows:
            print("(no users found)")
        for row in rows:
            print(tuple(row))
        return 0

    if len(argv) != 2:
        print(__doc__)
        return 2

    email, tier = argv[0], argv[1].upper()

    # Validate against the model enum so a typo can't poison the column
    # (the DB column is a native enum of the NAMES). Load base.py DIRECTLY
    # by file path: importing it via the package would pull in
    # ospra_os.database.__init__ -> connection.py, whose module-level
    # get_engine() call rejects non-Postgres URLs (breaks local/sqlite use)
    # and needlessly opens an app engine just to read an enum.
    import importlib.util

    base_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "ospra_os", "database", "base.py",
    )
    spec = importlib.util.spec_from_file_location("_ospra_db_base", base_path)
    base_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base_mod)

    valid = {t.name for t in base_mod.SubscriptionTier}
    if tier not in valid:
        print(f"ERROR: invalid tier {tier!r}. Valid tiers: {sorted(valid)}")
        return 2

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "UPDATE users SET subscription_tier = :t "
                "WHERE lower(email) = lower(:m) "
                "RETURNING id, email, subscription_tier"
            ),
            {"t": tier, "m": email},
        ).fetchall()

    if not rows:
        print(f"No user with email {email!r}. Run with --list to see accounts.")
        return 1

    for row in rows:
        print("updated:", tuple(row))
    print("NOTE: the user must log OUT and back IN for the new tier to apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
