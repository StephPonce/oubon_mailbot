"""
Credential health — expiry must be LOUD (discovery-reliability spec, Step 6).

Fail-if-reverted pins for the July 2026 incident class: both self-healers
existed but were silently disarmed (CJ refresh needs CJ_EMAIL+CJ_API_KEY;
the AE DS env token carried no refresh_token), so prod tokens died on
schedule and the catalog went 16 days stale with green cron checkmarks.
"""

from datetime import datetime, timedelta, timezone

import pytest

from ospra_os.core import credential_health as ch


CRED_VARS = [
    "CJ_ACCESS_TOKEN", "CJ_EMAIL", "CJ_API_KEY",
    "ALIEXPRESS_ACCESS_TOKEN", "ALIEXPRESS_APP_KEY",
    "ALIEXPRESS_APP_SECRET", "ALIEXPRESS_TRACKING_ID",
]


@pytest.fixture()
def clean_env(monkeypatch):
    for var in CRED_VARS:
        monkeypatch.delenv(var, raising=False)
    # Default: no DB row, DB readable.
    monkeypatch.setattr(
        "ospra_os.database.aliexpress_tokens.load_token", lambda api_type: None
    )
    return monkeypatch


def test_disarmed_cj_healer_reports_and_alerts(clean_env):
    """The spec's exact pin: token present, no email/api_key →
    {present: true, healer_armed: false} + a loud alert."""
    clean_env.setenv("CJ_ACCESS_TOKEN", "some-live-token")

    health = ch.credential_health()
    assert health["cj"] == {"present": True, "healer_armed": False}
    assert any("CJ" in a and "DISARMED" in a for a in health["alerts"])


def test_armed_cj_healer_no_alert(clean_env):
    clean_env.setenv("CJ_ACCESS_TOKEN", "some-live-token")
    clean_env.setenv("CJ_EMAIL", "ops@example.com")
    clean_env.setenv("CJ_API_KEY", "cjkey")

    health = ch.credential_health()
    assert health["cj"]["healer_armed"] is True
    assert not any("CJ" in a for a in health["alerts"])


def test_ae_env_token_without_db_refresh_is_the_june_trap(clean_env):
    """Env bootstrap token + no DB refresh row → refresh_seeded False and an
    alert: this exact configuration starved discovery from June 29."""
    clean_env.setenv("ALIEXPRESS_ACCESS_TOKEN", "stale-env-token")

    health = ch.credential_health()
    ds = health["aliexpress_ds"]
    assert ds["token_present"] is True
    assert ds["token_source"] == "env"
    assert ds["refresh_seeded"] is False
    assert any("refresh_token" in a for a in health["alerts"])


def test_ae_db_row_with_refresh_token_is_healthy(clean_env):
    expires = (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()
    clean_env.setattr(
        "ospra_os.database.aliexpress_tokens.load_token",
        lambda api_type: {
            "access_token": "tok", "refresh_token": "refresh",
            "expires_at": expires,
        },
    )
    health = ch.credential_health()
    ds = health["aliexpress_ds"]
    assert ds["token_source"] == "db"
    assert ds["refresh_seeded"] is True
    assert ds["days_to_expiry"] == pytest.approx(20, abs=0.1)
    assert not any("refresh_token" in a for a in health["alerts"])


def test_no_ds_token_at_all_is_not_the_trap(clean_env):
    """Unconfigured DS (no env, no DB) — affiliate fallback carries AE; the
    trap alert is specifically token-present-without-healer."""
    health = ch.credential_health()
    ds = health["aliexpress_ds"]
    assert ds["token_present"] is False
    assert ds["refresh_seeded"] is False
    assert not any("refresh_token" in a for a in health["alerts"])


def test_db_unreachable_reports_honestly_not_crash(clean_env):
    def boom(api_type):
        raise RuntimeError("db down")
    clean_env.setattr("ospra_os.database.aliexpress_tokens.load_token", boom)

    health = ch.credential_health()  # must not raise
    assert health["aliexpress_ds"]["db_readable"] is False


def test_no_secret_material_in_payload(clean_env):
    """/health is public — token values must never appear in the payload."""
    clean_env.setenv("CJ_ACCESS_TOKEN", "SECRET-CJ-TOKEN-VALUE")
    clean_env.setenv("ALIEXPRESS_ACCESS_TOKEN", "SECRET-AE-TOKEN-VALUE")
    clean_env.setenv("CJ_API_KEY", "SECRET-CJ-KEY")
    clean_env.setenv("CJ_EMAIL", "ops@example.com")

    health = ch.credential_health()
    assert "SECRET" not in repr(health)
    assert "ops@example.com" not in repr(health)


def test_warm_run_carries_alerts_and_main_exits_3(monkeypatch):
    """catalog_warm surfaces credential alerts in its result, and main()
    turns them into exit code 3 (credential debt ≠ sources dead (2))."""
    from ospra_os.tasks import catalog_warm as cw

    async def fake_run():
        return {
            "niches": 3, "discovered": 12, "new": 5, "seen": 7,
            "snapshots": 12, "by_niche": [],
            "credential_alerts": ["CJ healer DISARMED (...)"],
        }

    monkeypatch.setattr(cw.asyncio, "run", lambda coro: (coro.close() or {
        "niches": 3, "discovered": 12, "new": 5, "seen": 7,
        "snapshots": 12, "by_niche": [],
        "credential_alerts": ["CJ healer DISARMED (...)"],
    }))
    monkeypatch.setattr(cw, "run", fake_run)

    with pytest.raises(SystemExit) as exc:
        cw.main()
    assert exc.value.code == 3
