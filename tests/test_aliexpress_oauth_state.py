"""AliExpress OAuth callbacks must verify the CSRF state.

Both callbacks write a DEPLOYMENT-WIDE credential — the dropship token and the
affiliate token respectively. They previously accepted a `state` parameter and
never read it, so anyone could feed their own authorization code and have every
tenant's sourcing (or affiliate commission) run through their account.

These tests pin the guard at the function level: a forged/absent/expired state
is rejected before any token exchange happens.
"""

import time

import pytest

from ospra_os.aliexpress.routes import _make_oauth_state, _verify_oauth_state


def test_minted_state_verifies():
    assert _verify_oauth_state(_make_oauth_state()) is True


@pytest.mark.parametrize("bad", [
    None,
    "",
    "not-a-state",
    "only.two",
    "nonce.9999999999.deadbeef",          # right shape, wrong signature
    "a.b.c.d",                             # too many parts
])
def test_forged_states_rejected(bad):
    assert _verify_oauth_state(bad) is False


def test_expired_state_rejected():
    """A signature stays valid forever; the embedded expiry is what stops replay."""
    nonce, _expiry, _sig = _make_oauth_state().split(".")
    past = str(int(time.time()) - 60)
    # Re-sign with a past expiry so the signature is genuine and only the
    # deadline has passed — this is exactly a replayed old state.
    from ospra_os.aliexpress.routes import _hmac, _state_secret
    import hashlib
    sig = _hmac.new(
        _state_secret(), f"{nonce}.{past}".encode(), hashlib.sha256
    ).hexdigest()[:32]
    assert _verify_oauth_state(f"{nonce}.{past}.{sig}") is False


def test_signature_is_not_forgeable_without_the_secret():
    """Swapping the nonce while keeping a real signature must fail."""
    nonce, expiry, sig = _make_oauth_state().split(".")
    assert _verify_oauth_state(f"{nonce}x.{expiry}.{sig}") is False
    assert _verify_oauth_state(f"{nonce}.{int(expiry) + 1}.{sig}") is False


def test_callbacks_reject_before_token_exchange(monkeypatch):
    """The guard must run BEFORE any credential is written."""
    import asyncio

    from ospra_os.api import aliexpress_affiliate_oauth, aliexpress_oauth

    for mod, fn in (
        (aliexpress_oauth, aliexpress_oauth.oauth_callback),
        (aliexpress_affiliate_oauth, aliexpress_affiliate_oauth.affiliate_oauth_callback),
    ):
        # Any token save would be a failure — the guard should return first.
        def _boom(*_a, **_k):  # pragma: no cover - must never run
            raise AssertionError("token exchange reached with an invalid state")

        if hasattr(mod, "save_token"):
            monkeypatch.setattr(mod, "save_token", _boom, raising=False)

        resp = asyncio.run(fn(code="attacker-code", state="forged.1.2"))
        assert resp.status_code == 400
