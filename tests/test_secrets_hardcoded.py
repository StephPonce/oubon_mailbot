"""
Section A band 3 — hardcoded secrets/fallbacks + admin provisioning
(T4/T5 + is_admin).
"""

from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-hardcoded")


# ---------------------------------------------------------------------------
# T4 — whitelabel partner-admin gate uses the real admin dependency
# ---------------------------------------------------------------------------

class TestT4WhitelabelAdminGate:
    def test_placeholder_key_is_gone(self):
        """The literal-comparison gate (x_admin_key != "admin-key-placeholder")
        must not exist as CODE (comments documenting the old bug are fine)."""
        from ospra_os.whitelabel import routes as wl

        src = inspect.getsource(wl)
        assert 'x_admin_key != "admin-key-placeholder"' not in src
        assert 'Header(..., alias="x-admin-key")' not in src

    def test_gate_is_the_real_admin_dependency(self):
        from ospra_os.whitelabel import routes as wl
        from ospra_os.auth.jwt_auth import require_admin_user

        assert wl.require_admin is require_admin_user

    def test_placeholder_header_no_longer_grants_access(self, client):
        """The old magic header must not open partner-admin endpoints."""
        response = client.post(
            "/api/whitelabel/partners",
            headers={"x-admin-key": "admin-key-placeholder"},
            json={"company_name": "Evil Co", "contact_email": "e@x.com"},
        )
        assert response.status_code in (401, 403, 422)
        assert response.status_code != 200


# ---------------------------------------------------------------------------
# T5 — one JWT secret loader
# ---------------------------------------------------------------------------

class TestT5OneSecretLoader:
    def test_handler_uses_canonical_secret(self):
        from ospra_os.auth import jwt_auth, jwt_handler

        assert jwt_handler.JWT_SECRET_KEY == jwt_auth.SECRET_KEY

    def test_no_duplicate_dev_literals(self):
        """Only jwt_auth may carry the dev fallback literal."""
        import ospra_os.auth.jwt_handler as h
        import ospra_os.middleware.tier_enforcement as te

        for mod in (h, te):
            src = inspect.getsource(mod)
            assert "DO-NOT-USE-IN-PRODUCTION" not in src, mod.__name__

    def test_cross_module_token_verification(self):
        """A token minted by jwt_handler must verify in tier_enforcement's
        decode path (same secret). Pre-fix they used different dev literals."""
        from jose import jwt as jose_jwt
        from ospra_os.auth import jwt_auth, jwt_handler

        token = jose_jwt.encode({"sub": "1", "type": "access"},
                                jwt_handler.JWT_SECRET_KEY, algorithm="HS256")
        decoded = jose_jwt.decode(token, jwt_auth.SECRET_KEY, algorithms=["HS256"])
        assert decoded["sub"] == "1"


# ---------------------------------------------------------------------------
# is_admin flag — model, migration, and gates honor it
# ---------------------------------------------------------------------------

class TestAdminFlag:
    def test_user_model_has_is_admin_default_false(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from ospra_os.database.base import Base
        from ospra_os.database import User

        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(engine, tables=[User.__table__])
        session = sessionmaker(bind=engine)()
        session.add(User(email="u@x.com", name="U", password_hash="x"))
        session.commit()
        user = session.query(User).first()
        assert user.is_admin is False  # deny-by-default
        session.close()

    def test_migration_004_exists_and_chains(self):
        import importlib.util
        path = os.path.join(
            os.path.dirname(__file__), "..",
            "alembic", "versions", "20260713_2000_004_user_is_admin.py",
        )
        spec = importlib.util.spec_from_file_location("mig004", path)
        mig = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mig)
        assert mig.revision == "004"
        assert mig.down_revision == "003"

    def test_require_admin_user_honors_flag(self):
        """The User-object admin gate: flag off → 403, flag on → passes."""
        import asyncio
        from types import SimpleNamespace
        from fastapi import HTTPException
        from ospra_os.auth.jwt_auth import require_admin_user

        regular = SimpleNamespace(id=1, is_admin=False, is_superuser=False)
        with pytest.raises(HTTPException) as exc:
            asyncio.run(require_admin_user(user=regular))
        assert exc.value.status_code == 403

        admin = SimpleNamespace(id=2, is_admin=True, is_superuser=False)
        assert asyncio.run(require_admin_user(user=admin)) is admin

    def test_require_admin_checks_db_flag(self, db_session, test_user, monkeypatch):
        """The TokenPayload-based require_admin (monitoring router etc.) reads
        the DB is_admin flag — no more unreachable 'tier == admin' check."""
        import asyncio
        from fastapi import HTTPException
        from types import SimpleNamespace
        import ospra_os.database.connection as conn
        from ospra_os.auth.dependencies import require_admin

        # Point the dependency's session at the test DB.
        monkeypatch.setattr(conn, "get_session", lambda *a, **k: db_session)
        # Keep the dependency from closing the shared fixture session.
        monkeypatch.setattr(db_session, "close", lambda: None)

        payload = SimpleNamespace(user_id=test_user.id, tier="nest")

        # Not admin → 403.
        test_user.is_admin = False
        db_session.flush()
        with pytest.raises(HTTPException):
            asyncio.run(require_admin(user=payload))

        # Flip the DB flag → passes (no token re-mint needed).
        test_user.is_admin = True
        db_session.flush()
        result = asyncio.run(require_admin(user=payload))
        assert result is payload
