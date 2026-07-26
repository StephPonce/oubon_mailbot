"""
Credential health — expiry must be LOUD (discovery-reliability spec, Step 6).

Why this exists: in July 2026 the prod catalog went 16 days stale because the
cron's CJ and AliExpress tokens died ON SCHEDULE and nothing noticed. Both
self-healers existed but were silently DISARMED — CJ's refresh needs
CJ_EMAIL + CJ_API_KEY (absent), and the AE DS env token carried no
refresh_token (OAuth never completed). Standing rule born from it (CLAUDE.md):
env-pasted tokens are bootstrap-only; every credential must have an armed
refresh path or a loud expiry alert. A static secret is a scheduled outage.

This module is that alert. `credential_health()` reports, per credential:
present?, healer ARMED?, and days-to-expiry where knowable — plus a flat
`alerts` list for the load-bearing disarmed cases. It is invoked at
catalog_warm start (ALERT lines + non-zero exit AFTER the warm completes,
so the check itself never causes the outage it exists to prevent) and
exposed in /health (booleans/numbers only — no secret material ever).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def _days_until(expires_at_iso: Optional[str]) -> Optional[float]:
    if not expires_at_iso:
        return None
    try:
        dt = datetime.fromisoformat(expires_at_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return round((dt - datetime.now(timezone.utc)).total_seconds() / 86400, 1)
    except (TypeError, ValueError):
        return None


def credential_health() -> dict:
    """Inspect the load-bearing supplier credentials. Cheap (env reads + one
    guarded DB read), never raises, never returns secret material."""
    alerts: list[str] = []

    # ── CJ Dropshipping ──────────────────────────────────────────────────
    # Tokens expire ~15 days BY DESIGN. The 401 self-healer
    # (client._refresh_access_token) is armed only when CJ_EMAIL and
    # CJ_API_KEY are both set — with them, expiry stops mattering.
    cj_present = bool(os.getenv("CJ_ACCESS_TOKEN", "").strip())
    cj_armed = bool(
        os.getenv("CJ_EMAIL", "").strip() and os.getenv("CJ_API_KEY", "").strip()
    )
    cj = {"present": cj_present, "healer_armed": cj_armed}
    if not cj_armed:
        alerts.append(
            "CJ healer DISARMED (CJ_EMAIL/CJ_API_KEY unset): "
            + (
                "the current token will 401 at its ~15-day TTL and nothing can re-auth."
                if cj_present
                else "no token and no way to mint one — CJ sourcing is dead."
            )
        )

    # ── AliExpress DS (dropship OAuth) ───────────────────────────────────
    # The healer is a stored refresh_token (aliexpress_tokens, api_type=
    # dropship). An env ALIEXPRESS_ACCESS_TOKEN passes is_available() but
    # cannot self-heal — the exact trap that starved discovery in July.
    db_row = None
    db_error = False
    try:
        from ospra_os.database.aliexpress_tokens import load_token
        db_row = load_token("dropship")
    except Exception as exc:  # DB unreachable ⇒ report honestly, don't crash
        db_error = True
        logger.warning(f"[CRED-HEALTH] could not read aliexpress_tokens: {exc}")

    env_token = bool(os.getenv("ALIEXPRESS_ACCESS_TOKEN", "").strip())
    db_token = bool(db_row and db_row.get("access_token"))
    refresh_seeded = bool(db_row and db_row.get("refresh_token"))
    ae_ds = {
        "token_present": db_token or env_token,
        "token_source": "db" if db_token else ("env" if env_token else None),
        "refresh_seeded": refresh_seeded,
        "days_to_expiry": _days_until(db_row.get("expires_at")) if db_row else None,
        "db_readable": not db_error,
    }
    if ae_ds["token_present"] and not refresh_seeded:
        alerts.append(
            "AliExpress DS token has NO stored refresh_token (env bootstrap "
            "token): it will die on expiry and cannot self-heal — visit "
            "/aliexpress/auth/start?key=<AE_OAUTH_SETUP_KEY> to seed OAuth. "
            "(Affiliate fallback "
            "keeps AE sourcing alive meanwhile.)"
        )

    # ── AliExpress affiliate (app-signed, no OAuth token needed) ─────────
    ae_affiliate = {
        "configured": bool(
            os.getenv("ALIEXPRESS_APP_KEY", "").strip()
            and os.getenv("ALIEXPRESS_APP_SECRET", "").strip()
        ),
        # Informational: June 29 proved product.query tolerates an empty
        # tracking_id; a real one improves link attribution, not liveness.
        "tracking_id_set": bool(os.getenv("ALIEXPRESS_TRACKING_ID", "").strip()),
    }

    return {
        "cj": cj,
        "aliexpress_ds": ae_ds,
        "aliexpress_affiliate": ae_affiliate,
        "alerts": alerts,
    }
