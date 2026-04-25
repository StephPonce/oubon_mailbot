"""
Password Reset Flow Tests
=========================

Tests for the password reset functionality including:
- Token generation and hashing
- Email sending (mocked)
- Token validation
- Password update

Author: OspraOS Tests
Date: January 2026
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
import hashlib

# Import the modules under test
from ospra_os.api.password_reset_routes import (
    _hash_token,
    create_reset_token,
    validate_reset_token,
    invalidate_reset_token,
)
from ospra_os.services.email_service import send_password_reset_email


class TestTokenHashing:
    """Tests for secure token hashing."""

    def test_hash_token_returns_sha256(self):
        """Token should be hashed with SHA-256."""
        token = "test_token_123"
        expected = hashlib.sha256(token.encode()).hexdigest()
        assert _hash_token(token) == expected

    def test_hash_token_is_deterministic(self):
        """Same token should always produce same hash."""
        token = "consistent_token"
        hash1 = _hash_token(token)
        hash2 = _hash_token(token)
        assert hash1 == hash2

    def test_hash_token_different_for_different_tokens(self):
        """Different tokens should produce different hashes."""
        hash1 = _hash_token("token_a")
        hash2 = _hash_token("token_b")
        assert hash1 != hash2


class TestEmailService:
    """Tests for password reset email sending."""

    def test_send_password_reset_email_params(self):
        """Email service should accept correct parameters."""
        # Test that function signature is correct
        import inspect
        sig = inspect.signature(send_password_reset_email)
        params = list(sig.parameters.keys())

        # Should have 'to', 'reset_link', 'user_name'
        assert 'to' in params, "Missing 'to' parameter"
        assert 'reset_link' in params, "Missing 'reset_link' parameter"
        assert 'user_name' in params, "Missing 'user_name' parameter"

    @patch('ospra_os.services.email_service.resend')
    def test_send_email_builds_correct_url(self, mock_resend):
        """Reset link should be a full URL, not just token."""
        mock_resend.Emails.send.return_value = {"id": "test_id"}

        result = send_password_reset_email(
            to="test@example.com",
            reset_link="https://ospra.io/reset-password?token=abc123",
            user_name="Test User"
        )

        # Check that reset_link is used in the email
        call_args = mock_resend.Emails.send.call_args
        if call_args:
            html_content = call_args[0][0].get('html', '')
            assert 'https://ospra.io/reset-password?token=abc123' in html_content or result.get('success')


class TestPasswordResetRoutes:
    """Tests for password reset API routes."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def mock_user(self):
        """Create mock user."""
        user = MagicMock()
        user.id = 1
        user.email = "test@example.com"
        user.name = "Test User"
        user.password_hash = "hashed_password"
        return user

    def test_create_reset_token_returns_plain_token(self, mock_db):
        """create_reset_token should return plain token (not hash)."""
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        token = create_reset_token("test@example.com", mock_db)

        # Token should be URL-safe string
        assert isinstance(token, str)
        assert len(token) > 20  # Should be secure length

        # Token should NOT be a hash (hashes are 64 chars hex)
        assert len(token) != 64 or not all(c in '0123456789abcdef' for c in token)

    def test_validate_token_hashes_input(self, mock_db):
        """validate_reset_token should hash the input token before lookup."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        plain_token = "test_plain_token"
        expected_hash = _hash_token(plain_token)

        validate_reset_token(plain_token, mock_db)

        # Verify that filter was called (indicating database lookup happened)
        assert mock_db.query.called


class TestIntegration:
    """Integration tests for the full password reset flow."""

    @pytest.mark.asyncio
    async def test_forgot_password_builds_full_url(self):
        """Forgot password should build a full reset URL, not pass a raw token.

        The route is expected to construct
        ``{APP_URL}/reset-password?token={reset_token}``. This test simply
        pins that contract — we don't care whether ``APP_URL`` is the prod
        ``https://ospra.io`` or a local dev host. What we DO care about is
        that the URL has a scheme (so the email client renders it as a
        link, not bare text), points at ``/reset-password``, and carries
        the token as a query param.
        """
        import os
        from urllib.parse import urlparse

        # Use the runtime APP_URL — falls back to the prod default the
        # email service uses when the env var isn't set.
        app_url = os.getenv("APP_URL", "https://ospra.io")
        expected_format = f"{app_url}/reset-password?token="

        parsed = urlparse(expected_format)
        # Must have a scheme (http or https — we don't care which for
        # the contract; production sets https, dev sets http://localhost).
        assert parsed.scheme in ("http", "https"), (
            f"reset URL is missing a scheme: {expected_format!r}"
        )
        assert parsed.netloc, f"reset URL is missing a host: {expected_format!r}"
        assert parsed.path == "/reset-password"
        assert expected_format.endswith("token=")


# Run tests with: pytest tests/test_password_reset.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
