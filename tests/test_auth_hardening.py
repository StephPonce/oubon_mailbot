"""
Section C band 4 — hardening regression tests (T41/T52/T53).

T52: password fields had no max_length → bcrypt-DoS via huge input.
T53: Gmail OAuth callback attached every connected account to a hardcoded
     user_id=1 (multi-tenant break + IDOR).
T41: trends endpoints' auth posture — decided as "authenticated", enforced.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-hardening")


# ---------------------------------------------------------------------------
# T52 — password length caps (bcrypt DoS)
# ---------------------------------------------------------------------------

class TestT52PasswordCaps:
    def test_register_password_capped(self):
        from pydantic import ValidationError
        from ospra_os.auth.routes import RegisterRequest

        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", password="x" * 129)

    def test_reset_password_capped(self):
        from pydantic import ValidationError
        from ospra_os.auth.routes import ResetPasswordRequest

        with pytest.raises(ValidationError):
            ResetPasswordRequest(token="t", password="x" * 129)

    def test_login_password_capped(self):
        from pydantic import ValidationError
        from ospra_os.auth.routes import LoginRequest

        with pytest.raises(ValidationError):
            LoginRequest(email="a@b.com", password="x" * 129)

    def test_normal_password_still_accepted(self):
        from ospra_os.auth.routes import RegisterRequest, ResetPasswordRequest

        assert RegisterRequest(email="a@b.com", password="a-good-password-1")
        assert ResetPasswordRequest(token="t", password="a-good-password-1")


# ---------------------------------------------------------------------------
# T53 — Gmail OAuth binds to the real user, not hardcoded user_id=1
# ---------------------------------------------------------------------------

class TestT53GmailOAuthBinding:
    def test_uid_sign_verify_roundtrip(self):
        from ospra_os.gmail import routes

        signed = routes._sign_uid(42)
        assert routes._verify_uid(signed) == 42

    def test_forged_uid_cookie_rejected(self):
        from ospra_os.gmail import routes

        # Attacker tries to bind to user 1 without a valid signature.
        assert routes._verify_uid("1.deadbeef") is None
        assert routes._verify_uid("1") is None
        assert routes._verify_uid("") is None
        assert routes._verify_uid(None) is None

    def test_tampered_uid_rejected(self):
        from ospra_os.gmail import routes

        signed = routes._sign_uid(42)
        uid_part, sig = signed.rsplit(".", 1)
        forged = f"999.{sig}"  # keep victim's signature, swap the id
        assert routes._verify_uid(forged) is None

    def test_no_hardcoded_user_id_1_in_callback(self):
        """The literal 'User.id == 1' / 'id=1' attach must be gone."""
        import inspect
        from ospra_os.gmail import routes

        src = inspect.getsource(routes.callback)
        assert "User.id == 1" not in src
        assert "id=1," not in src
        # It must resolve the user from the verified cookie instead.
        assert "_verify_uid" in src

    def test_start_requires_auth(self, client):
        assert client.get("/gmail/auth/start").status_code in (401, 403)


# ---------------------------------------------------------------------------
# T41 — trends endpoints require authentication
# ---------------------------------------------------------------------------

class TestT41TrendsAuth:
    @pytest.mark.parametrize("path", [
        "/api/trends/live",
        "/api/trends/movers",
        "/api/trends/breakouts",
        "/api/trends/product/abc",
        "/api/trends/heatmap",
    ])
    def test_trends_require_auth(self, client, path):
        assert client.get(path).status_code in (401, 403), f"{path} not gated"

    def test_trends_ws_rejects_without_token(self, client):
        """The /ws/trends socket must close on a missing/invalid token."""
        from starlette.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/trends") as ws:
                ws.receive_text()

    def test_trends_ws_rejects_bad_token(self, client):
        from starlette.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/trends?token=garbage") as ws:
                ws.receive_text()
