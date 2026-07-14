"""
Section A band 1 — secrets encrypted at rest (T7/T8/T9/T10).

Tokens and credentials used to sit in the DB as plaintext. These tests assert
they are encrypted on write, decrypt on read, that the migration-safe mixed
old/new path works (a legacy plaintext row reads fine and re-encrypts), and
that production fails CLOSED instead of silently persisting plaintext.
"""

from __future__ import annotations

import os

import pytest
from cryptography.fernet import Fernet

# A real, stable key so encryption is deterministic across the test process.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-encryption")
os.environ["CREDENTIALS_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

from ospra_os.security.credential_encryption import encrypt_field, decrypt_field


@pytest.fixture
def sqlite_db(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(f"sqlite:///{tmp_path/'tok.db'}")
    return engine, sessionmaker(bind=engine)


# ---------------------------------------------------------------------------
# T7 — AliExpress tokens
# ---------------------------------------------------------------------------

class TestT7AliexpressTokens:
    @pytest.fixture
    def tok_module(self, sqlite_db, monkeypatch):
        engine, factory = sqlite_db
        import ospra_os.database.aliexpress_tokens as tok
        from ospra_os.database.base import Base
        Base.metadata.create_all(engine, tables=[tok.AliExpressToken.__table__])
        monkeypatch.setattr(tok, "engine", engine)
        monkeypatch.setattr(tok, "SessionLocal", factory)
        return tok

    def test_token_stored_encrypted(self, tok_module):
        tok = tok_module
        assert tok.save_token("dropship", "at-secret-123", "rt-secret-456", 3600)

        # Read the raw column — it must NOT be the plaintext token.
        session = tok.SessionLocal()
        row = session.query(tok.AliExpressToken).filter_by(api_type="dropship").first()
        session.close()
        assert row.access_token != "at-secret-123"
        assert row.refresh_token != "rt-secret-456"
        # And it must decrypt back to the original.
        assert decrypt_field(row.access_token) == "at-secret-123"

    def test_load_decrypts(self, tok_module):
        tok = tok_module
        tok.save_token("dropship", "at-secret-123", "rt-secret-456", 3600)
        payload = tok.load_token("dropship")
        assert payload["access_token"] == "at-secret-123"
        assert payload["refresh_token"] == "rt-secret-456"

    def test_status_has_no_token_preview(self, tok_module):
        tok = tok_module
        tok.save_token("dropship", "at-secret-123", "rt-secret-456", 3600)
        status = tok.get_token_status()
        # The old access_token_preview leak (first 20 chars) must be gone.
        assert "access_token_preview" not in status["dropship"]
        assert "at-secret-123"[:20] not in str(status)

    def test_legacy_plaintext_row_reads_and_reencrypts(self, tok_module):
        """MIGRATION SAFETY: a row written BEFORE encryption (raw plaintext)
        must read back correctly, then be encrypted on the next save."""
        tok = tok_module
        # Simulate a legacy plaintext row by writing the column directly.
        session = tok.SessionLocal()
        session.add(tok.AliExpressToken(
            api_type="affiliate", access_token="legacy-plain-at",
            refresh_token="legacy-plain-rt", expires_in=3600,
        ))
        session.commit()
        session.close()

        # Reads fine (decrypt_field tolerates plaintext).
        payload = tok.load_token("affiliate")
        assert payload["access_token"] == "legacy-plain-at"

        # Re-save → now stored encrypted.
        tok.save_token("affiliate", "legacy-plain-at", "legacy-plain-rt", 3600)
        session = tok.SessionLocal()
        row = session.query(tok.AliExpressToken).filter_by(api_type="affiliate").first()
        session.close()
        assert row.access_token != "legacy-plain-at"  # now encrypted
        assert decrypt_field(row.access_token) == "legacy-plain-at"


# ---------------------------------------------------------------------------
# T8 — TikTok tokens
# ---------------------------------------------------------------------------

class TestT8TiktokTokens:
    @pytest.fixture
    def tok_module(self, sqlite_db, monkeypatch):
        engine, factory = sqlite_db
        import ospra_os.database.tiktok_tokens as tok
        from ospra_os.database.base import Base
        Base.metadata.create_all(engine, tables=[tok.TikTokToken.__table__])
        monkeypatch.setattr(tok, "engine", engine)
        monkeypatch.setattr(tok, "SessionLocal", factory)
        return tok

    def test_token_stored_encrypted(self, tok_module):
        tok = tok_module
        tok.save_token("tt-access-secret", "tt-refresh-secret", 3600)
        session = tok.SessionLocal()
        row = session.query(tok.TikTokToken).first()
        session.close()
        assert row.access_token != "tt-access-secret"
        assert decrypt_field(row.access_token) == "tt-access-secret"

    def test_load_and_get_access_token_decrypt(self, tok_module):
        tok = tok_module
        tok.save_token("tt-access-secret", "tt-refresh-secret", 3600)
        assert tok.get_access_token() == "tt-access-secret"
        assert tok.load_token()["refresh_token"] == "tt-refresh-secret"

    def test_null_refresh_token_handled(self, tok_module):
        tok = tok_module
        tok.save_token("tt-access-secret", None, 3600)
        assert tok.load_token()["refresh_token"] is None

    def test_legacy_plaintext_reads(self, tok_module):
        tok = tok_module
        session = tok.SessionLocal()
        session.add(tok.TikTokToken(
            access_token="legacy-tt-plain", refresh_token="legacy-tt-rt", expires_in=3600,
        ))
        session.commit()
        session.close()
        assert tok.get_access_token() == "legacy-tt-plain"


# ---------------------------------------------------------------------------
# T9 — store/amazon models fail CLOSED in prod (no silent plaintext)
# ---------------------------------------------------------------------------

class TestT9FailClosed:
    def test_store_set_credentials_raises_in_prod_without_encryption(self, monkeypatch):
        from ospra_os.database import store_models

        # Simulate the encryption module failing to import.
        monkeypatch.setattr(store_models, "_get_encryption", lambda: (None, None))
        monkeypatch.setenv("ENVIRONMENT", "production")

        store = store_models.Store()
        with pytest.raises(Exception):  # CredentialEncryptionError / RuntimeError
            store.set_credentials({"access_token": "secret"})

    def test_store_set_credentials_encrypts_normally(self):
        from ospra_os.database import store_models
        store = store_models.Store()
        store.set_credentials({"access_token": "shpat_secret"})
        # Stored value is not the raw dict/plaintext.
        assert "shpat_secret" not in str(store.credentials)
        assert store.get_credentials()["access_token"] == "shpat_secret"

    def test_amazon_set_credentials_raises_in_prod_without_encryption(self, monkeypatch):
        from ospra_os.database import amazon_models

        monkeypatch.setattr(amazon_models, "_get_field_encryption", lambda: (None, None))
        monkeypatch.setenv("ENVIRONMENT", "production")

        acct = amazon_models.AmazonSellerAccount() if hasattr(amazon_models, "AmazonSellerAccount") \
            else _first_amazon_model(amazon_models)()
        with pytest.raises(Exception):
            acct.set_sensitive_credentials(refresh_token="secret")


def _first_amazon_model(mod):
    """Find the model class exposing set_sensitive_credentials."""
    import inspect
    for _, obj in inspect.getmembers(mod, inspect.isclass):
        if hasattr(obj, "set_sensitive_credentials"):
            return obj
    raise AssertionError("no amazon model with set_sensitive_credentials")


# ---------------------------------------------------------------------------
# T10 — whitelabel smtp_password + custom_ai_keys real encryption helpers
# ---------------------------------------------------------------------------

class TestT10EncryptedHelpers:
    def test_smtp_password_roundtrip_encrypted(self):
        from ospra_os.database.whitelabel_models import WhiteLabelEmailSettings
        s = WhiteLabelEmailSettings()
        s.set_smtp_password("super-secret-smtp")
        assert s.smtp_password != "super-secret-smtp"  # encrypted at rest
        assert s.get_smtp_password() == "super-secret-smtp"

    def test_user_ai_key_roundtrip_encrypted(self):
        from ospra_os.database import User
        u = User()
        u.set_ai_key("openai", "sk-real-secret-key")
        assert "sk-real-secret-key" not in str(u.custom_ai_keys)  # encrypted
        assert u.get_ai_key("openai") == "sk-real-secret-key"
