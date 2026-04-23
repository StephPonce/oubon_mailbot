"""
Tests for API Response Helpers
==============================

Tests the standardized response format utilities.
"""

import pytest
from fastapi.responses import JSONResponse

from ospra_os.api.responses import (
    success_response,
    error_response,
    paginated_response,
    list_response,
    created_response,
    deleted_response,
    ErrorCodes,
)


class TestSuccessResponse:
    """Tests for success_response helper"""

    def test_basic_success(self):
        """Test basic success response with data"""
        result = success_response(data={"key": "value"})

        assert result["success"] is True
        assert result["data"] == {"key": "value"}

    def test_success_with_message(self):
        """Test success response with message"""
        result = success_response(data=[], message="Items retrieved")

        assert result["success"] is True
        assert result["data"] == []
        assert result["message"] == "Items retrieved"

    def test_success_with_meta(self):
        """Test success response with metadata"""
        meta = {"total": 100, "page": 1}
        result = success_response(data=[], meta=meta)

        assert result["success"] is True
        assert result["meta"] == meta

    def test_success_no_data(self):
        """Test success response with no data"""
        result = success_response(message="Operation completed")

        assert result["success"] is True
        assert "data" not in result
        assert result["message"] == "Operation completed"

    def test_success_with_none_data(self):
        """Test that None data is not included"""
        result = success_response(data=None, message="OK")

        assert result["success"] is True
        assert "data" not in result


class TestErrorResponse:
    """Tests for error_response helper"""

    def test_basic_error(self):
        """Test basic error response"""
        result = error_response("Something went wrong")

        assert isinstance(result, JSONResponse)
        assert result.status_code == 400

    def test_error_with_code(self):
        """Test error response with error code"""
        result = error_response(
            "Validation failed",
            error_code=ErrorCodes.VALIDATION_ERROR
        )

        assert isinstance(result, JSONResponse)
        # JSONResponse body is bytes, we can check status
        assert result.status_code == 400

    def test_error_custom_status(self):
        """Test error response with custom status code"""
        result = error_response(
            "Not found",
            error_code=ErrorCodes.NOT_FOUND,
            status_code=404
        )

        assert result.status_code == 404

    def test_error_with_details(self):
        """Test error response with additional details"""
        result = error_response(
            "Invalid input",
            details={"field": "email", "issue": "Invalid format"}
        )

        assert isinstance(result, JSONResponse)


class TestPaginatedResponse:
    """Tests for paginated_response helper"""

    def test_basic_pagination(self):
        """Test basic paginated response"""
        data = [{"id": 1}, {"id": 2}]
        result = paginated_response(data, total=100, page=1, per_page=20)

        assert result["success"] is True
        assert result["data"] == data
        assert result["meta"]["pagination"]["total"] == 100
        assert result["meta"]["pagination"]["page"] == 1
        assert result["meta"]["pagination"]["per_page"] == 20
        assert result["meta"]["pagination"]["total_pages"] == 5
        assert result["meta"]["pagination"]["has_next"] is True
        assert result["meta"]["pagination"]["has_prev"] is False

    def test_pagination_last_page(self):
        """Test pagination on last page"""
        data = [{"id": 99}, {"id": 100}]
        result = paginated_response(data, total=100, page=5, per_page=20)

        assert result["meta"]["pagination"]["has_next"] is False
        assert result["meta"]["pagination"]["has_prev"] is True

    def test_pagination_middle_page(self):
        """Test pagination on middle page"""
        data = [{"id": 41}]
        result = paginated_response(data, total=100, page=3, per_page=20)

        assert result["meta"]["pagination"]["has_next"] is True
        assert result["meta"]["pagination"]["has_prev"] is True

    def test_pagination_single_page(self):
        """Test pagination with only one page"""
        data = [{"id": 1}]
        result = paginated_response(data, total=1, page=1, per_page=20)

        assert result["meta"]["pagination"]["total_pages"] == 1
        assert result["meta"]["pagination"]["has_next"] is False
        assert result["meta"]["pagination"]["has_prev"] is False

    def test_pagination_empty_results(self):
        """Test pagination with no results"""
        result = paginated_response([], total=0, page=1, per_page=20)

        assert result["data"] == []
        assert result["meta"]["pagination"]["total"] == 0
        assert result["meta"]["pagination"]["total_pages"] == 0

    def test_pagination_with_message(self):
        """Test pagination with optional message"""
        result = paginated_response(
            [{"id": 1}],
            total=1,
            page=1,
            per_page=20,
            message="Products retrieved"
        )

        assert result["message"] == "Products retrieved"

    def test_pagination_calculation(self):
        """Test total_pages calculation with different totals"""
        # 21 items with 20 per page = 2 pages
        result = paginated_response([], total=21, page=1, per_page=20)
        assert result["meta"]["pagination"]["total_pages"] == 2

        # 20 items with 20 per page = 1 page
        result = paginated_response([], total=20, page=1, per_page=20)
        assert result["meta"]["pagination"]["total_pages"] == 1

        # 19 items with 20 per page = 1 page
        result = paginated_response([], total=19, page=1, per_page=20)
        assert result["meta"]["pagination"]["total_pages"] == 1


class TestListResponse:
    """Tests for list_response helper"""

    def test_list_response(self):
        """Test list response with items"""
        items = [{"id": 1}, {"id": 2}, {"id": 3}]
        result = list_response(items)

        assert result["success"] is True
        assert result["data"] == items
        assert result["meta"]["count"] == 3

    def test_empty_list_response(self):
        """Test list response with no items"""
        result = list_response([])

        assert result["success"] is True
        assert result["data"] == []
        assert result["meta"]["count"] == 0

    def test_list_response_with_message(self):
        """Test list response with message"""
        result = list_response([{"id": 1}], message="Found 1 item")

        assert result["message"] == "Found 1 item"


class TestCreatedResponse:
    """Tests for created_response helper"""

    def test_created_response(self):
        """Test created response"""
        data = {"id": 123, "name": "New Resource"}
        result = created_response(data)

        assert result["success"] is True
        assert result["data"] == data
        assert result["message"] == "Resource created successfully"

    def test_created_with_custom_message(self):
        """Test created response with custom message"""
        result = created_response(
            {"id": 1},
            message="User account created"
        )

        assert result["message"] == "User account created"


class TestDeletedResponse:
    """Tests for deleted_response helper"""

    def test_deleted_response(self):
        """Test deleted response"""
        result = deleted_response()

        assert result["success"] is True
        assert result["message"] == "Resource deleted successfully"

    def test_deleted_with_id(self):
        """Test deleted response with resource ID"""
        result = deleted_response(resource_id=123)

        assert result["deleted_id"] == 123

    def test_deleted_custom_message(self):
        """Test deleted response with custom message"""
        result = deleted_response(message="Product removed from store")

        assert result["message"] == "Product removed from store"


class TestErrorCodes:
    """Tests for ErrorCodes enum"""

    def test_auth_codes_exist(self):
        """Test authentication error codes exist"""
        assert ErrorCodes.AUTH_REQUIRED == "AUTH_REQUIRED"
        assert ErrorCodes.INVALID_TOKEN == "INVALID_TOKEN"
        assert ErrorCodes.TOKEN_EXPIRED == "TOKEN_EXPIRED"
        assert ErrorCodes.INSUFFICIENT_PERMISSIONS == "INSUFFICIENT_PERMISSIONS"

    def test_validation_codes_exist(self):
        """Test validation error codes exist"""
        assert ErrorCodes.VALIDATION_ERROR == "VALIDATION_ERROR"
        assert ErrorCodes.INVALID_INPUT == "INVALID_INPUT"
        assert ErrorCodes.MISSING_FIELD == "MISSING_FIELD"

    def test_resource_codes_exist(self):
        """Test resource error codes exist"""
        assert ErrorCodes.NOT_FOUND == "NOT_FOUND"
        assert ErrorCodes.ALREADY_EXISTS == "ALREADY_EXISTS"
        assert ErrorCodes.CONFLICT == "CONFLICT"

    def test_rate_limit_code_exists(self):
        """Test rate limiting error code exists"""
        assert ErrorCodes.RATE_LIMIT_EXCEEDED == "RATE_LIMIT_EXCEEDED"

    def test_server_codes_exist(self):
        """Test server error codes exist"""
        assert ErrorCodes.INTERNAL_ERROR == "INTERNAL_ERROR"
        assert ErrorCodes.SERVICE_UNAVAILABLE == "SERVICE_UNAVAILABLE"
        assert ErrorCodes.EXTERNAL_SERVICE_ERROR == "EXTERNAL_SERVICE_ERROR"
