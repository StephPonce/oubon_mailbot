"""
Tests for API Dependencies
===========================

Tests for shared dependencies including pagination.
"""

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from ospra_os.api.dependencies import (
    PaginationParams,
    get_pagination,
    paginated_response,
)


class TestPaginationParams:
    """Tests for PaginationParams dataclass"""

    def test_create_pagination_params(self):
        """Test creating pagination params"""
        params = PaginationParams(page=2, per_page=25, offset=25)

        assert params.page == 2
        assert params.per_page == 25
        assert params.offset == 25

    def test_skip_property(self):
        """Test skip property is alias for offset"""
        params = PaginationParams(page=3, per_page=10, offset=20)

        assert params.skip == 20
        assert params.skip == params.offset


class TestGetPagination:
    """Tests for get_pagination dependency

    Note: get_pagination uses FastAPI Query() defaults, so we test via HTTP
    or by calling with explicit values (the Query defaults resolve at runtime).
    """

    def test_custom_page(self):
        """Test custom page number"""
        # Call with explicit values (bypasses Query defaults)
        result = get_pagination(page=5, per_page=20)

        assert result.page == 5
        assert result.offset == 80  # (5-1) * 20

    def test_custom_per_page(self):
        """Test custom items per page"""
        result = get_pagination(page=1, per_page=50)

        assert result.per_page == 50
        assert result.offset == 0

    def test_offset_calculation(self):
        """Test offset is calculated correctly"""
        # Page 1: offset 0
        assert get_pagination(page=1, per_page=10).offset == 0
        # Page 2: offset 10
        assert get_pagination(page=2, per_page=10).offset == 10
        # Page 3: offset 20
        assert get_pagination(page=3, per_page=10).offset == 20

        # Different per_page
        assert get_pagination(page=2, per_page=25).offset == 25
        assert get_pagination(page=3, per_page=25).offset == 50


class TestPaginatedResponseFunction:
    """Tests for paginated_response helper in dependencies"""

    def test_basic_response(self):
        """Test basic paginated response"""
        pagination = PaginationParams(page=1, per_page=20, offset=0)
        data = [{"id": 1}, {"id": 2}]

        result = paginated_response(data, total=100, pagination=pagination)

        assert result["success"] is True
        assert result["data"] == data
        assert result["total"] == 100
        assert result["page"] == 1
        assert result["per_page"] == 20
        assert result["total_pages"] == 5
        assert result["has_next"] is True
        assert result["has_prev"] is False

    def test_last_page(self):
        """Test pagination on last page"""
        pagination = PaginationParams(page=5, per_page=20, offset=80)

        result = paginated_response([], total=100, pagination=pagination)

        assert result["has_next"] is False
        assert result["has_prev"] is True

    def test_single_page(self):
        """Test single page results"""
        pagination = PaginationParams(page=1, per_page=20, offset=0)

        result = paginated_response([{"id": 1}], total=1, pagination=pagination)

        assert result["total_pages"] == 1
        assert result["has_next"] is False
        assert result["has_prev"] is False

    def test_zero_results(self):
        """Test empty results"""
        pagination = PaginationParams(page=1, per_page=20, offset=0)

        result = paginated_response([], total=0, pagination=pagination)

        assert result["total"] == 0
        assert result["total_pages"] == 0
        assert result["has_next"] is False
        assert result["has_prev"] is False


class TestPaginationDependencyIntegration:
    """Integration tests for pagination as FastAPI dependency"""

    @pytest.fixture
    def app(self):
        """Create test FastAPI app with pagination endpoint"""
        from ospra_os.api.dependencies import Pagination

        app = FastAPI()

        @app.get("/items")
        def list_items(pagination: Pagination):
            return {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "offset": pagination.offset,
            }

        return app

    @pytest.fixture
    def test_client(self, app):
        """Create test client"""
        return TestClient(app)

    def test_default_pagination(self, test_client):
        """Test default pagination values via API"""
        response = test_client.get("/items")

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["per_page"] == 20
        assert data["offset"] == 0

    def test_custom_pagination(self, test_client):
        """Test custom pagination values via API"""
        response = test_client.get("/items?page=3&per_page=50")

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 3
        assert data["per_page"] == 50
        assert data["offset"] == 100  # (3-1) * 50

    def test_page_validation_min(self, test_client):
        """Test page minimum validation"""
        response = test_client.get("/items?page=0")

        assert response.status_code == 422  # Validation error

    def test_per_page_validation_max(self, test_client):
        """Test per_page maximum validation"""
        response = test_client.get("/items?per_page=200")

        assert response.status_code == 422  # Validation error (max is 100)

    def test_per_page_validation_min(self, test_client):
        """Test per_page minimum validation"""
        response = test_client.get("/items?per_page=0")

        assert response.status_code == 422  # Validation error (min is 1)
