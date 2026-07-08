"""
Tests for New Ospra OS Modules
==============================

Tests for the modules created during the Phase 1-3 improvements.

Run with: pytest tests/test_new_modules.py -v
"""

import os
import json
import tempfile
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


# =============================================================================
# SAFE JSON TESTS
# =============================================================================

class TestSafeJson:
    """Tests for safe JSON file operations."""

    def test_safe_read_json_missing_file(self):
        """Reading missing file should return default."""
        from ospra_os.utils.safe_json import safe_read_json

        result = safe_read_json("/nonexistent/file.json", default={"key": "value"})
        assert result == {"key": "value"}

    def test_safe_read_json_empty_default(self):
        """Reading missing file with no default returns empty dict."""
        from ospra_os.utils.safe_json import safe_read_json

        result = safe_read_json("/nonexistent/file.json")
        assert result == {}

    def test_safe_write_and_read_json(self):
        """Writing and reading JSON should preserve data."""
        from ospra_os.utils.safe_json import safe_read_json, safe_write_json

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            data = {"name": "test", "value": 123, "nested": {"key": "val"}}

            # Write
            result = safe_write_json(temp_path, data)
            assert result is True

            # Read back
            loaded = safe_read_json(temp_path)
            assert loaded == data

        finally:
            os.unlink(temp_path)

    def test_safe_read_json_invalid_json(self):
        """Reading invalid JSON should return default."""
        from ospra_os.utils.safe_json import safe_read_json

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("not valid json {{{")
            temp_path = f.name

        try:
            result = safe_read_json(temp_path, default={"error": True})
            assert result == {"error": True}
        finally:
            os.unlink(temp_path)

    def test_safe_update_json(self):
        """Updating JSON file atomically."""
        from ospra_os.utils.safe_json import safe_write_json, safe_update_json

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            # Create initial file
            safe_write_json(temp_path, {"count": 1})

            # Update it
            def increment(data):
                data["count"] += 1
                return data

            result = safe_update_json(temp_path, increment)
            assert result is True

            # Verify
            from ospra_os.utils.safe_json import safe_read_json
            loaded = safe_read_json(temp_path)
            assert loaded["count"] == 2

        finally:
            os.unlink(temp_path)


# =============================================================================
# ENVIRONMENT VALIDATOR TESTS
# =============================================================================

class TestEnvValidator:
    """Tests for environment variable validation."""

    def test_is_production_development(self):
        """Development environment should not be production."""
        from ospra_os.core.env_validator import is_production

        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=True):
            assert is_production() is False

    def test_is_production_explicit(self):
        """Explicit production setting should be detected."""
        from ospra_os.core.env_validator import is_production

        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=True):
            assert is_production() is True

        with patch.dict(os.environ, {"ENVIRONMENT": "prod"}, clear=True):
            assert is_production() is True

    def test_is_production_cloud_platforms(self):
        """Cloud platform environment variables should indicate production."""
        from ospra_os.core.env_validator import is_production

        # Render
        with patch.dict(os.environ, {"RENDER": "true"}, clear=True):
            assert is_production() is True

        # Railway
        with patch.dict(os.environ, {"RAILWAY_ENVIRONMENT": "production"}, clear=True):
            assert is_production() is True

    def test_validate_var_type_string(self):
        """String type should accept any value."""
        from ospra_os.core.env_validator import validate_var_type, VarType

        valid, error = validate_var_type("anything", VarType.STRING)
        assert valid is True
        assert error == ""

    def test_validate_var_type_integer(self):
        """Integer type should validate correctly."""
        from ospra_os.core.env_validator import validate_var_type, VarType

        # Valid
        valid, error = validate_var_type("123", VarType.INTEGER)
        assert valid is True

        # Invalid
        valid, error = validate_var_type("abc", VarType.INTEGER)
        assert valid is False
        assert "integer" in error

    def test_validate_var_type_url(self):
        """URL type should validate correctly."""
        from ospra_os.core.env_validator import validate_var_type, VarType

        # Valid URLs
        valid, _ = validate_var_type("https://example.com", VarType.URL)
        assert valid is True

        valid, _ = validate_var_type("postgresql://localhost/db", VarType.URL)
        assert valid is True

        # Invalid
        valid, error = validate_var_type("not-a-url", VarType.URL)
        assert valid is False

    def test_get_missing_required_vars(self):
        """Should identify missing required variables."""
        from ospra_os.core.env_validator import get_missing_required_vars

        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=True):
            missing = get_missing_required_vars()
            # In development, fewer vars are required
            assert isinstance(missing, list)


# =============================================================================
# API RESPONSE TESTS
# =============================================================================

class TestApiResponse:
    """Tests for standardized API responses."""

    def test_success_response_basic(self):
        """Success response should have correct structure."""
        from ospra_os.utils.api_response import success_response

        response = success_response(data={"key": "value"})

        assert response["success"] is True
        assert response["data"] == {"key": "value"}
        assert "timestamp" in response

    def test_success_response_with_message(self):
        """Success response should include message when provided."""
        from ospra_os.utils.api_response import success_response

        response = success_response(data=None, message="Operation completed")

        assert response["success"] is True
        assert response["message"] == "Operation completed"

    def test_error_response(self):
        """Error response should have correct structure."""
        from ospra_os.utils.api_response import error_response

        response = error_response(
            message="Something went wrong",
            code="TEST_ERROR",
            status_code=400
        )

        assert response.status_code == 400
        body = json.loads(response.body)
        assert body["success"] is False
        assert body["error"]["message"] == "Something went wrong"
        assert body["error"]["code"] == "TEST_ERROR"
        assert "error_id" in body["error"]

    def test_paginated_response(self):
        """Paginated response should have correct metadata."""
        from ospra_os.utils.api_response import paginated_response

        response = paginated_response(
            items=[1, 2, 3],
            total=10,
            page=1,
            per_page=3
        )

        assert response["success"] is True
        assert response["data"] == [1, 2, 3]
        assert response["pagination"]["total"] == 10
        assert response["pagination"]["total_pages"] == 4
        assert response["pagination"]["has_next"] is True
        assert response["pagination"]["has_prev"] is False

    def test_not_found_response(self):
        """Not found response should be 404."""
        from ospra_os.utils.api_response import not_found_response

        response = not_found_response("Product", 123)

        assert response.status_code == 404
        body = json.loads(response.body)
        assert body["error"]["code"] == "NOT_FOUND"
        assert "123" in body["error"]["message"]


# =============================================================================
# PAGINATION TESTS
# =============================================================================

class TestPagination:
    """Tests for pagination utilities."""

    def test_default_pagination(self):
        """Default pagination should have sensible defaults."""
        from ospra_os.utils.pagination import safe_pagination, DEFAULT_PAGE_SIZE

        params = safe_pagination()

        assert params.limit == DEFAULT_PAGE_SIZE
        assert params.offset == 0
        assert params.page == 1

    def test_pagination_with_page(self):
        """Pagination should calculate offset from page."""
        from ospra_os.utils.pagination import safe_pagination

        params = safe_pagination(page=3, per_page=10)

        assert params.page == 3
        assert params.limit == 10
        assert params.offset == 20  # (3-1) * 10

    def test_pagination_max_limit(self):
        """Pagination should enforce maximum limit."""
        from ospra_os.utils.pagination import safe_pagination, MAX_PAGE_SIZE

        params = safe_pagination(per_page=1000)

        assert params.limit == MAX_PAGE_SIZE

    def test_pagination_max_offset(self):
        """Pagination should enforce maximum offset."""
        from ospra_os.utils.pagination import safe_pagination, MAX_OFFSET

        params = safe_pagination(page=10000, per_page=100)

        assert params.offset <= MAX_OFFSET


# =============================================================================
# REQUEST TRACING TESTS
# =============================================================================

class TestRequestTracing:
    """Tests for request tracing."""

    def test_get_request_id_default(self):
        """Request ID should be None when no request active."""
        from ospra_os.observability.request_tracing import get_request_id

        # Outside of request context, should be None
        request_id = get_request_id()
        assert request_id is None

    def test_tracing_logger(self):
        """TracingLogger should format messages correctly."""
        from ospra_os.observability.request_tracing import TracingLogger, _request_id

        logger = TracingLogger("test")

        # Without request ID
        message = logger._format_message("Test message")
        assert message == "Test message"

        # With request ID
        _request_id.set("abc123")
        try:
            message = logger._format_message("Test message")
            assert "[abc123]" in message
            assert "Test message" in message
        finally:
            _request_id.set(None)


# =============================================================================
# RETRY LOGIC TESTS
# =============================================================================

class TestRetryLogic:
    """Tests for retry utilities."""

    @pytest.mark.asyncio
    async def test_retry_success_first_try(self):
        """Function that succeeds should not retry."""
        from ospra_os.utils.retry import retry_with_backoff

        call_count = 0

        @retry_with_backoff(max_retries=3)
        async def succeeds():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await succeeds()

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_eventually_succeeds(self):
        """Function should retry and eventually succeed."""
        from ospra_os.utils.retry import retry_with_backoff

        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"

        result = await fails_twice()

        assert result == "success"
        assert call_count == 3

    def test_idempotency_key_generation(self):
        """Same arguments should generate same key."""
        from ospra_os.utils.retry import generate_idempotency_key

        key1 = generate_idempotency_key("arg1", "arg2", kwarg="value")
        key2 = generate_idempotency_key("arg1", "arg2", kwarg="value")
        key3 = generate_idempotency_key("arg1", "arg3", kwarg="value")

        assert key1 == key2
        assert key1 != key3


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
