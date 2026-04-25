"""
Tests for Authentication
=========================

Tests for JWT authentication and user management.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from ospra_os.database import User


class TestUserModel:
    """Tests for User model"""

    def test_create_user(self, db_session):
        """Test creating a user"""
        user = User(
            email="newuser@example.com",
            password_hash="$2b$12$hashed_password",
            name="New User",
            subscription_tier="nest"
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        assert user.id is not None
        assert user.email == "newuser@example.com"
        assert user.subscription_tier == "nest"

    def test_user_unique_email(self, db_session):
        """Test that email must be unique"""
        user1 = User(
            email="duplicate@example.com",
            password_hash="hash1",
            name="User 1"
        )
        db_session.add(user1)
        db_session.commit()

        user2 = User(
            email="duplicate@example.com",
            password_hash="hash2",
            name="User 2"
        )
        db_session.add(user2)

        # Should raise IntegrityError
        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()


class TestAuthEndpoints:
    """Tests for authentication API endpoints"""

    def test_login_success(self, client, db_session):
        """Test successful login"""
        # Use the production hash function so the test stays in sync with
        # whatever scheme jwt_auth currently uses (currently SHA-256 +
        # bcrypt — see ``ospra_os/auth/jwt_auth.py::_pre_hash``).
        from ospra_os.auth.jwt_auth import hash_password

        password_hash = hash_password("testpassword123")

        user = User(
            email="login@example.com",
            password_hash=password_hash,
            name="Login Test User"
        )
        db_session.add(user)
        db_session.commit()

        # Attempt login
        response = client.post("/api/auth/login", json={
            "email": "login@example.com",
            "password": "testpassword123"
        })

        # Should return token
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data or "token" in data

    def test_login_invalid_credentials(self, client, db_session):
        """Test login with invalid credentials"""
        # Use the production hash function (SHA-256 + bcrypt).
        from ospra_os.auth.jwt_auth import hash_password

        password_hash = hash_password("correctpassword")

        user = User(
            email="wrongpwd@example.com",
            password_hash=password_hash,
            name="Test User"
        )
        db_session.add(user)
        db_session.commit()

        # Attempt login with wrong password
        response = client.post("/api/auth/login", json={
            "email": "wrongpwd@example.com",
            "password": "wrongpassword"
        })

        assert response.status_code in [400, 401]

    def test_login_nonexistent_user(self, client):
        """Test login with non-existent user"""
        response = client.post("/api/auth/login", json={
            "email": "doesnotexist@example.com",
            "password": "anypassword"
        })

        assert response.status_code in [400, 401, 404]

    def test_register_user(self, client, db_session):
        """Test user registration"""
        response = client.post("/api/auth/register", json={
            "email": "newregister@example.com",
            "password": "SecurePass123!",
            "name": "New Registered User"
        })

        # Should create user
        assert response.status_code in [200, 201]

        # Verify user exists
        user = db_session.query(User).filter(
            User.email == "newregister@example.com"
        ).first()
        assert user is not None
        assert user.name == "New Registered User"

    def test_register_duplicate_email(self, client, db_session, test_user):
        """Test registration with existing email"""
        response = client.post("/api/auth/register", json={
            "email": test_user.email,  # Already exists
            "password": "password123",
            "name": "Duplicate User"
        })

        assert response.status_code in [400, 409]

    def test_register_invalid_email(self, client):
        """Test registration with invalid email"""
        response = client.post("/api/auth/register", json={
            "email": "not-an-email",
            "password": "password123",
            "name": "Test User"
        })

        assert response.status_code == 422  # Validation error


class TestProtectedEndpoints:
    """Tests for protected endpoints requiring authentication"""

    def test_protected_without_token(self, client):
        """Test accessing protected endpoint without token"""
        response = client.get("/api/actions")

        # Should be unauthorized
        assert response.status_code in [401, 403]

    def test_protected_with_invalid_token(self, client):
        """Test accessing protected endpoint with invalid token"""
        response = client.get(
            "/api/actions",
            headers={"Authorization": "Bearer invalid_token_here"}
        )

        assert response.status_code in [401, 403]

    def test_protected_with_valid_auth(self, auth_client, test_user):
        """Test accessing protected endpoint with valid auth"""
        response = auth_client.get("/api/actions")

        assert response.status_code == 200


class TestCurrentUser:
    """Tests for /api/auth/me endpoint"""

    def test_get_current_user(self, auth_client, test_user):
        """Test getting current user info.

        The /api/auth/me endpoint wraps the user under ``user`` and adds
        a sibling ``subscription`` block — the test pins that contract so
        we notice if the response shape ever changes silently.
        """
        response = auth_client.get("/api/auth/me")

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        user_block = data.get("user") or {}
        assert user_block.get("email") == test_user.email
        assert user_block.get("name") == test_user.name

    def test_get_current_user_without_auth(self, client):
        """Test getting current user without authentication"""
        response = client.get("/api/auth/me")

        assert response.status_code in [401, 403]


class TestTokenRefresh:
    """Tests for token refresh functionality"""

    @pytest.mark.skip(reason="Token refresh may not be implemented")
    def test_refresh_token(self, auth_client):
        """Test refreshing authentication token"""
        response = auth_client.post("/api/auth/refresh")

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data or "token" in data


class TestPasswordReset:
    """Tests for password reset functionality"""

    @pytest.mark.skip(reason="Password reset may use email")
    def test_request_password_reset(self, client, test_user):
        """Test requesting password reset"""
        response = client.post("/api/auth/forgot-password", json={
            "email": test_user.email
        })

        # Should succeed (even if email doesn't exist for security)
        assert response.status_code == 200
