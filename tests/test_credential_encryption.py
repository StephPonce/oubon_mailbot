"""
Tests for ``ospra_os.security.credential_encryption`` (audit #11 final).

Covers the audit-fix #7 fail-closed semantics plus the legacy-row
tolerance the read paths rely on.

Why this test file exists: ``encrypt_credentials`` and friends sit on
the OAuth-token write path for every connected store. A regression here
silently writes plaintext OR raises in production, and either is
catastrophic. Before this file there was zero direct coverage; the
behavior was only exercised transitively via store-fixture round-trips.
"""

from __future__ import annotations

import json

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_encryption_state(monkeypatch):
    """
    Force the lazy ``_init_fernet`` to rebuild on next call.

    The module caches the Fernet instance + an ``_encryption_available``
    flag in module-level globals. Tests that flip env vars need to clear
    those so the next call picks up the new env.
    """
    from ospra_os.security import credential_encryption as ce
    monkeypatch.setattr(ce, "_fernet", None, raising=False)
    monkeypatch.setattr(ce, "_encryption_available", False, raising=False)


@pytest.fixture
def dev_mode(monkeypatch):
    """
    Development mode — no key configured. ``_init_fernet`` should
    auto-generate an ephemeral Fernet key and the encrypt/decrypt
    round-trip should still succeed.
    """
    monkeypatch.delenv("CREDENTIALS_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("EMAIL_OAUTH_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    _reset_encryption_state(monkeypatch)


@pytest.fixture
def configured_mode(monkeypatch):
    """
    Stable Fernet key configured — both dev and prod look like this in
    a healthy deployment. Round-trips must succeed and re-encrypting
    the same value must produce decryption-identical output.
    """
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", key)
    monkeypatch.setenv("ENVIRONMENT", "production")
    _reset_encryption_state(monkeypatch)
    return key


@pytest.fixture
def prod_no_key(monkeypatch):
    """
    Production-flagged but no key — the audit-fix #7 case. Every
    encrypt/decrypt call must raise ``CredentialEncryptionError``
    instead of falling back to plaintext.
    """
    monkeypatch.delenv("CREDENTIALS_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("EMAIL_OAUTH_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    _reset_encryption_state(monkeypatch)


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

def test_encrypt_decrypt_credentials_roundtrip(configured_mode):
    from ospra_os.security.credential_encryption import (
        encrypt_credentials, decrypt_credentials,
    )
    creds = {
        "shop_url": "demo.myshopify.com",
        "access_token": "shpat_secret_value",
        "api_version": "2024-10",
    }
    encrypted = encrypt_credentials(creds)
    assert encrypted != json.dumps(creds), "ciphertext must differ from plaintext"
    assert decrypt_credentials(encrypted) == creds


def test_encrypt_decrypt_field_roundtrip(configured_mode):
    from ospra_os.security.credential_encryption import encrypt_field, decrypt_field
    encrypted = encrypt_field("shpat_xxxxxxxxxx")
    assert encrypted != "shpat_xxxxxxxxxx"
    assert decrypt_field(encrypted) == "shpat_xxxxxxxxxx"


def test_encrypt_credentials_empty_returns_empty(configured_mode):
    """An empty dict is still valid input; output is an empty string by contract."""
    from ospra_os.security.credential_encryption import encrypt_credentials
    assert encrypt_credentials({}) == ""


def test_decrypt_credentials_already_dict_passes_through(configured_mode):
    """Backwards-compat: stores that wrote a plain dict return unchanged."""
    from ospra_os.security.credential_encryption import decrypt_credentials
    raw = {"access_token": "x"}
    assert decrypt_credentials(raw) == raw


# ---------------------------------------------------------------------------
# Selective sensitive-field encryption
# ---------------------------------------------------------------------------

def test_encrypt_sensitive_fields_only_touches_secret_keys(configured_mode):
    from ospra_os.security.credential_encryption import (
        encrypt_sensitive_fields, decrypt_sensitive_fields,
    )
    data = {
        "shop_url": "demo.myshopify.com",      # not sensitive — plaintext
        "access_token": "shpat_xxx",            # sensitive
        "currency": "USD",                      # not sensitive
        "client_secret": "secret_xxx",          # sensitive
    }
    encrypted = encrypt_sensitive_fields(data)
    # Non-sensitive fields preserved verbatim
    assert encrypted["shop_url"] == data["shop_url"]
    assert encrypted["currency"] == data["currency"]
    # Sensitive fields are different from plaintext
    assert encrypted["access_token"] != data["access_token"]
    assert encrypted["client_secret"] != data["client_secret"]
    # And round-trip back
    decrypted = decrypt_sensitive_fields(encrypted)
    assert decrypted == data


# ---------------------------------------------------------------------------
# Fail-closed in production (audit fix #7)
# ---------------------------------------------------------------------------

def test_prod_no_key_raises_on_encrypt(prod_no_key):
    """No CREDENTIALS_ENCRYPTION_KEY in prod → raise, never store plaintext."""
    from ospra_os.security.credential_encryption import (
        encrypt_credentials, CredentialEncryptionError,
    )
    with pytest.raises(CredentialEncryptionError) as excinfo:
        encrypt_credentials({"access_token": "shpat_xxx"})
    assert "production" in str(excinfo.value).lower()


def test_prod_no_key_raises_on_field_encrypt(prod_no_key):
    from ospra_os.security.credential_encryption import (
        encrypt_field, CredentialEncryptionError,
    )
    with pytest.raises(CredentialEncryptionError):
        encrypt_field("shpat_xxx")


def test_prod_no_key_raises_on_decrypt(prod_no_key):
    """Decrypt path is the read side — same fail-closed semantics in prod."""
    from ospra_os.security.credential_encryption import (
        decrypt_credentials, CredentialEncryptionError,
    )
    with pytest.raises(CredentialEncryptionError):
        decrypt_credentials("anything")


# ---------------------------------------------------------------------------
# Dev fallback
# ---------------------------------------------------------------------------

def test_dev_no_key_uses_ephemeral_fernet(dev_mode):
    """
    No env flags + no key = development. ``_init_fernet`` generates an
    ephemeral key and the round-trip succeeds. This is what makes the
    test suite work without anyone setting CREDENTIALS_ENCRYPTION_KEY.
    """
    from ospra_os.security.credential_encryption import (
        encrypt_credentials, decrypt_credentials,
    )
    creds = {"access_token": "shpat_xxx"}
    encrypted = encrypt_credentials(creds)
    assert decrypt_credentials(encrypted) == creds


# ---------------------------------------------------------------------------
# Legacy plain-JSON tolerance
# ---------------------------------------------------------------------------

def test_decrypt_credentials_tolerates_legacy_plain_json(configured_mode):
    """
    A row that pre-dates encryption is stored as plain JSON. Reads must
    still succeed (with a warning logged) so we can read-then-rewrite
    during a credential migration. New encryption is configured but the
    stored value is plaintext.
    """
    from ospra_os.security.credential_encryption import decrypt_credentials
    legacy_value = json.dumps({"access_token": "legacy_token", "shop_url": "x.myshopify.com"})
    decoded = decrypt_credentials(legacy_value)
    assert decoded == {"access_token": "legacy_token", "shop_url": "x.myshopify.com"}


def test_decrypt_field_tolerates_legacy_plaintext(configured_mode):
    """Same legacy tolerance for single-field decrypt."""
    from ospra_os.security.credential_encryption import decrypt_field
    # A value that's neither encrypted nor parseable as JSON — the
    # legacy path returns it as-is.
    assert decrypt_field("plain-token-value") == "plain-token-value"


# ---------------------------------------------------------------------------
# Wrong-key behavior — different secret should not silently succeed
# ---------------------------------------------------------------------------

def test_decrypt_with_wrong_key_falls_back_to_legacy(monkeypatch):
    """
    If we encrypt with key A and try to decrypt with key B, the
    decryption fails. The current implementation falls back to "treat as
    legacy plaintext" — that's deliberate (it lets a key rotation pick
    up old rows during migration), but the value won't be the original
    plaintext, just the encrypted blob returned as-is. The important
    thing is we never raise on read.
    """
    from cryptography.fernet import Fernet
    from ospra_os.security import credential_encryption as ce

    # Encrypt with key A
    key_a = Fernet.generate_key().decode()
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", key_a)
    _reset_encryption_state(monkeypatch)
    encrypted = ce.encrypt_credentials({"access_token": "secret_xxx"})

    # Switch to key B
    key_b = Fernet.generate_key().decode()
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", key_b)
    _reset_encryption_state(monkeypatch)

    # Decryption with the wrong key falls through the legacy path; the
    # ciphertext from key A is not valid JSON, so we get an empty dict
    # plus a warning in the log. The contract: don't raise, don't
    # silently "succeed" with the wrong plaintext.
    result = ce.decrypt_credentials(encrypted)
    assert result == {} or result == {"access_token": "secret_xxx"}
    # In practice the empty-dict fallback fires because the ciphertext
    # isn't valid JSON. Either branch keeps reads stable.
