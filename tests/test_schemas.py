"""
Tests for Pydantic API Schemas
===============================

Tests for request/response validation schemas.
"""

import pytest
from pydantic import ValidationError

# Import from the schemas.py file (not the schemas/ package)
# We need to import specific modules directly
import importlib.util
import sys
import os

# Load the schemas.py file directly since it's shadowed by schemas/ package
schemas_path = os.path.join(
    os.path.dirname(__file__),
    '..', 'ospra_os', 'api', 'schemas.py'
)
spec = importlib.util.spec_from_file_location("request_schemas", schemas_path)
request_schemas = importlib.util.module_from_spec(spec)
spec.loader.exec_module(request_schemas)

# Import from the loaded module
StandardResponse = request_schemas.StandardResponse
PaginationParams = request_schemas.PaginationParams
PaginatedResponse = request_schemas.PaginatedResponse
paginate_list = request_schemas.paginate_list
PlatformCredentials = request_schemas.PlatformCredentials
ShopifyDeployRequest = request_schemas.ShopifyDeployRequest
AliExpressSearchRequest = request_schemas.AliExpressSearchRequest
AliExpressFulfillOrderRequest = request_schemas.AliExpressFulfillOrderRequest


class TestStandardResponse:
    """Tests for StandardResponse schema"""

    def test_success_response(self):
        """Test creating success response"""
        response = StandardResponse(
            success=True,
            message="Operation completed",
            data={"id": 1}
        )

        assert response.success is True
        assert response.message == "Operation completed"
        assert response.data == {"id": 1}

    def test_error_response(self):
        """Test creating error response"""
        response = StandardResponse(
            success=False,
            error="Something went wrong"
        )

        assert response.success is False
        assert response.error == "Something went wrong"


class TestPaginationParams:
    """Tests for PaginationParams schema"""

    def test_default_values(self):
        """Test default pagination values"""
        params = PaginationParams()

        assert params.page == 1
        assert params.per_page == 20
        assert params.sort_order == "desc"

    def test_custom_values(self):
        """Test custom pagination values"""
        params = PaginationParams(
            page=5,
            per_page=50,
            sort_by="created_at",
            sort_order="asc"
        )

        assert params.page == 5
        assert params.per_page == 50
        assert params.sort_by == "created_at"
        assert params.sort_order == "asc"

    def test_page_validation_min(self):
        """Test page minimum validation"""
        with pytest.raises(ValidationError):
            PaginationParams(page=0)

    def test_page_validation_max(self):
        """Test page maximum validation"""
        with pytest.raises(ValidationError):
            PaginationParams(page=20000)

    def test_per_page_validation_min(self):
        """Test per_page minimum validation"""
        with pytest.raises(ValidationError):
            PaginationParams(per_page=0)

    def test_per_page_validation_max(self):
        """Test per_page maximum validation"""
        with pytest.raises(ValidationError):
            PaginationParams(per_page=200)

    def test_sort_order_validation(self):
        """Test sort_order must be asc or desc"""
        with pytest.raises(ValidationError):
            PaginationParams(sort_order="invalid")


class TestPaginatedResponse:
    """Tests for PaginatedResponse schema"""

    def test_create_factory(self):
        """Test create factory method"""
        items = [{"id": 1}, {"id": 2}]

        response = PaginatedResponse.create(
            items=items,
            total=100,
            page=1,
            per_page=20
        )

        assert response.success is True
        assert response.data == items
        assert response.total == 100
        assert response.page == 1
        assert response.per_page == 20
        assert response.total_pages == 5
        assert response.has_next is True
        assert response.has_prev is False

    def test_last_page(self):
        """Test last page flags"""
        response = PaginatedResponse.create(
            items=[],
            total=100,
            page=5,
            per_page=20
        )

        assert response.has_next is False
        assert response.has_prev is True

    def test_single_page(self):
        """Test single page case"""
        response = PaginatedResponse.create(
            items=[{"id": 1}],
            total=1,
            page=1,
            per_page=20
        )

        assert response.total_pages == 1
        assert response.has_next is False
        assert response.has_prev is False


class TestPaginateList:
    """Tests for paginate_list helper function"""

    def test_basic_pagination(self):
        """Test basic list pagination"""
        items = list(range(50))

        result = paginate_list(items, page=1, per_page=10)

        assert result["data"] == list(range(10))
        assert result["total"] == 50
        assert result["total_pages"] == 5
        assert result["has_next"] is True
        assert result["has_prev"] is False

    def test_middle_page(self):
        """Test middle page pagination"""
        items = list(range(50))

        result = paginate_list(items, page=3, per_page=10)

        assert result["data"] == list(range(20, 30))
        assert result["has_next"] is True
        assert result["has_prev"] is True

    def test_last_page(self):
        """Test last page pagination"""
        items = list(range(50))

        result = paginate_list(items, page=5, per_page=10)

        assert result["data"] == list(range(40, 50))
        assert result["has_next"] is False
        assert result["has_prev"] is True

    def test_partial_last_page(self):
        """Test last page with fewer items"""
        items = list(range(45))  # 45 items, 10 per page = 5 pages

        result = paginate_list(items, page=5, per_page=10)

        assert len(result["data"]) == 5  # Only 5 items on last page
        assert result["data"] == list(range(40, 45))

    def test_empty_list(self):
        """Test empty list pagination"""
        result = paginate_list([], page=1, per_page=10)

        assert result["data"] == []
        assert result["total"] == 0
        assert result["total_pages"] == 0


class TestPlatformCredentials:
    """Tests for PlatformCredentials schema"""

    def test_basic_credentials(self):
        """Test basic credentials"""
        creds = PlatformCredentials(
            api_key="test_key",
            api_secret="test_secret"
        )

        assert creds.api_key == "test_key"
        assert creds.api_secret == "test_secret"

    def test_extra_fields_allowed(self):
        """Test extra fields are allowed"""
        creds = PlatformCredentials(
            api_key="test_key",
            custom_field="custom_value"
        )

        # Extra fields should be allowed due to Config
        assert creds.api_key == "test_key"


class TestShopifyDeployRequest:
    """Tests for ShopifyDeployRequest schema"""

    def test_with_product_id(self):
        """Test deploy with product_id"""
        request = ShopifyDeployRequest(product_id="123")

        assert request.product_id == "123"
        assert request.product_data is None

    def test_with_product_data(self):
        """Test deploy with product_data"""
        request = ShopifyDeployRequest(
            product_data={
                "title": "Test Product",
                "price": 29.99,
                "description": "A test product"
            }
        )

        assert request.product_data["title"] == "Test Product"
        assert request.product_data["price"] == 29.99

    def test_product_data_validation_missing_title(self):
        """Test product_data validation - missing title"""
        with pytest.raises(ValidationError) as exc:
            ShopifyDeployRequest(
                product_data={"price": 29.99}  # Missing title
            )

        assert "title" in str(exc.value)

    def test_product_data_validation_missing_price(self):
        """Test product_data validation - missing price"""
        with pytest.raises(ValidationError) as exc:
            ShopifyDeployRequest(
                product_data={"title": "Test"}  # Missing price
            )

        assert "price" in str(exc.value)


class TestAliExpressSearchRequest:
    """Tests for AliExpressSearchRequest schema"""

    def test_basic_search(self):
        """Test basic search request"""
        request = AliExpressSearchRequest(keywords="wireless earbuds")

        assert request.keywords == "wireless earbuds"
        assert request.sort_by == "SALE_PRICE_ASC"  # Default
        assert request.page_size == 20  # Default
        assert request.ship_to_country == "US"  # Default

    def test_custom_search_params(self):
        """Test custom search parameters"""
        request = AliExpressSearchRequest(
            keywords="phone case",
            category_id="100003070",
            min_price=5.0,
            max_price=20.0,
            sort_by="LAST_VOLUME_DESC",
            page_size=50
        )

        assert request.min_price == 5.0
        assert request.max_price == 20.0
        assert request.sort_by == "LAST_VOLUME_DESC"
        assert request.page_size == 50

    def test_keywords_required(self):
        """Test keywords is required"""
        with pytest.raises(ValidationError):
            AliExpressSearchRequest()

    def test_keywords_min_length(self):
        """Test keywords minimum length"""
        with pytest.raises(ValidationError):
            AliExpressSearchRequest(keywords="")

    def test_keywords_max_length(self):
        """Test keywords maximum length"""
        with pytest.raises(ValidationError):
            AliExpressSearchRequest(keywords="x" * 300)

    def test_price_validation_negative(self):
        """Test price cannot be negative"""
        with pytest.raises(ValidationError):
            AliExpressSearchRequest(keywords="test", min_price=-5.0)

    def test_price_validation_max(self):
        """Test price maximum"""
        with pytest.raises(ValidationError):
            AliExpressSearchRequest(keywords="test", max_price=20000)

    def test_sort_by_validation(self):
        """Test sort_by must be valid option"""
        with pytest.raises(ValidationError):
            AliExpressSearchRequest(keywords="test", sort_by="INVALID_SORT")

    def test_page_size_validation(self):
        """Test page_size bounds"""
        with pytest.raises(ValidationError):
            AliExpressSearchRequest(keywords="test", page_size=0)

        with pytest.raises(ValidationError):
            AliExpressSearchRequest(keywords="test", page_size=100)


class TestAliExpressFulfillOrderRequest:
    """Tests for AliExpressFulfillOrderRequest schema"""

    def test_valid_request(self):
        """Test valid fulfillment request"""
        request = AliExpressFulfillOrderRequest(
            order_id="ORD-123",
            product_id="ALI-456",
            quantity=2,
            shipping_address={
                "name": "John Doe",
                "address1": "123 Main St",
                "city": "New York",
                "country": "US",
                "zip": "10001"
            }
        )

        assert request.order_id == "ORD-123"
        assert request.quantity == 2

    def test_missing_shipping_field(self):
        """Test validation of shipping address fields"""
        with pytest.raises(ValidationError) as exc:
            AliExpressFulfillOrderRequest(
                order_id="ORD-123",
                product_id="ALI-456",
                quantity=1,
                shipping_address={
                    "name": "John Doe",
                    "address1": "123 Main St",
                    # Missing city, country, zip
                }
            )

        assert "city" in str(exc.value) or "country" in str(exc.value) or "zip" in str(exc.value)

    def test_quantity_validation(self):
        """Test quantity bounds"""
        with pytest.raises(ValidationError):
            AliExpressFulfillOrderRequest(
                order_id="ORD-123",
                product_id="ALI-456",
                quantity=0,  # Must be at least 1
                shipping_address={
                    "name": "John Doe",
                    "address1": "123 Main St",
                    "city": "New York",
                    "country": "US",
                    "zip": "10001"
                }
            )
