"""
Amazon SP-API Client - GROK RECOMMENDATION #16

Amazon Selling Partner API integration for FBA operations.

Features:
- OAuth 2.0 token management (LWA - Login with Amazon)
- AWS Signature Version 4 for request signing
- Rate limiting and retry logic
- Comprehensive API coverage:
  - Catalog Items API (product search)
  - Listings API (manage listings)
  - Orders API (order management)
  - FBA Inventory API (inventory tracking)
  - FBA Inbound API (shipments)
  - Product Fees API (fee calculation)
  - Reports API (performance data)
  - Pricing API (buy box, competitive pricing)

Requirements:
- python-amazon-sp-api (pip install python-amazon-sp-api)
OR manual implementation with requests + AWS signature

Documentation:
https://developer-docs.amazon.com/sp-api/
"""

import os
import time
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass

import requests
from requests.auth import AuthBase

logger = logging.getLogger(__name__)


@dataclass
class AmazonCredentials:
    """Amazon SP-API credentials"""

    # LWA (Login with Amazon) OAuth credentials
    lwa_client_id: str
    lwa_client_secret: str

    # SP-API credentials
    refresh_token: str

    # AWS IAM credentials for request signing
    aws_access_key: str
    aws_secret_key: str
    role_arn: Optional[str] = None

    # Marketplace
    marketplace_id: str = "ATVPDKIKX0DER"  # Default: US


class AWSAuthV4(AuthBase):
    """
    AWS Signature Version 4 request signing.

    Required for all SP-API requests.
    """

    def __init__(
        self,
        access_key: str,
        secret_key: str,
        service: str = "execute-api",
        region: str = "us-east-1"
    ):
        self.access_key = access_key
        self.secret_key = secret_key
        self.service = service
        self.region = region

    def __call__(self, request):
        """Sign the request with AWS SigV4"""
        # Simplified - use python-amazon-sp-api for production
        # or implement full AWS SigV4 signing

        # Add required AWS headers
        request.headers['x-amz-date'] = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        request.headers['x-amz-access-token'] = getattr(self, 'access_token', '')

        return request


class AmazonSPAPIClient:
    """
    Amazon Selling Partner API client.

    Handles authentication, rate limiting, and API calls for Amazon FBA operations.

    Usage:
        credentials = AmazonCredentials(
            lwa_client_id="amzn1.application-oa2-client.xxx",
            lwa_client_secret="xxx",
            refresh_token="Atzr|xxx",
            aws_access_key="AKIA...",
            aws_secret_key="xxx",
            marketplace_id="ATVPDKIKX0DER"
        )

        client = AmazonSPAPIClient(credentials)

        # Search catalog
        products = client.search_catalog(keywords="yoga mat")

        # Get listing
        listing = client.get_listing(seller_sku="YOGA-MAT-001")

        # Get orders
        orders = client.get_orders(created_after="2025-01-01T00:00:00Z")
    """

    # SP-API endpoints by region
    ENDPOINTS = {
        "us-east-1": "https://sellingpartnerapi-na.amazon.com",
        "eu-west-1": "https://sellingpartnerapi-eu.amazon.com",
        "us-west-2": "https://sellingpartnerapi-fe.amazon.com"
    }

    # LWA token endpoint
    LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"

    # Rate limits (requests per second by API)
    RATE_LIMITS = {
        "catalog": 2,      # 2 req/sec
        "listings": 5,     # 5 req/sec
        "orders": 0.0167,  # 1 req/min
        "inventory": 2,    # 2 req/sec
        "shipments": 2,    # 2 req/sec
    }

    def __init__(self, credentials: AmazonCredentials, region: str = "us-east-1"):
        self.credentials = credentials
        self.region = region
        self.base_url = self.ENDPOINTS.get(region, self.ENDPOINTS["us-east-1"])

        # Token management
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

        # Rate limiting
        self._last_request_time: Dict[str, float] = {}

        logger.info(f"AmazonSPAPIClient initialized for region: {region}")

    # ========================================================================
    # AUTHENTICATION
    # ========================================================================

    def get_access_token(self, force_refresh: bool = False) -> str:
        """
        Get LWA access token (OAuth 2.0).

        Uses refresh token to obtain short-lived access token.
        Caches token until expiration.

        Args:
            force_refresh: Force token refresh even if cached

        Returns:
            Access token string
        """

        # Return cached token if still valid
        if not force_refresh and self._access_token and self._token_expires_at:
            if datetime.utcnow() < self._token_expires_at - timedelta(minutes=5):
                return self._access_token

        logger.info("Refreshing Amazon LWA access token")

        try:
            response = requests.post(
                self.LWA_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.credentials.refresh_token,
                    "client_id": self.credentials.lwa_client_id,
                    "client_secret": self.credentials.lwa_client_secret
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

            response.raise_for_status()
            token_data = response.json()

            self._access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 3600)  # Default 1 hour
            self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            logger.info(f"Access token refreshed, expires in {expires_in}s")
            return self._access_token

        except Exception as e:
            logger.error(f"Failed to refresh access token: {e}")
            raise

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get headers with access token for SP-API requests"""
        token = self.get_access_token()
        return {
            "x-amz-access-token": token,
            "Content-Type": "application/json"
        }

    # ========================================================================
    # RATE LIMITING
    # ========================================================================

    def _wait_for_rate_limit(self, api_type: str):
        """
        Enforce rate limits for API calls.

        Args:
            api_type: API type (catalog, listings, orders, etc.)
        """

        rate_limit = self.RATE_LIMITS.get(api_type, 1)
        min_interval = 1.0 / rate_limit if rate_limit > 0 else 60

        last_request = self._last_request_time.get(api_type, 0)
        time_since_last = time.time() - last_request

        if time_since_last < min_interval:
            wait_time = min_interval - time_since_last
            logger.debug(f"Rate limiting {api_type}: waiting {wait_time:.2f}s")
            time.sleep(wait_time)

        self._last_request_time[api_type] = time.time()

    # ========================================================================
    # HTTP REQUEST WRAPPER
    # ========================================================================

    def _request(
        self,
        method: str,
        endpoint: str,
        api_type: str = "catalog",
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        retry_count: int = 3
    ) -> Dict[str, Any]:
        """
        Make authenticated SP-API request with rate limiting and retry.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path (e.g., "/catalog/2022-04-01/items")
            api_type: API type for rate limiting
            params: Query parameters
            json_data: JSON body
            retry_count: Number of retries on failure

        Returns:
            Response JSON
        """

        # Rate limiting
        self._wait_for_rate_limit(api_type)

        # Build URL
        url = f"{self.base_url}{endpoint}"

        # Headers
        headers = self._get_auth_headers()

        # AWS Signature (simplified - use python-amazon-sp-api for production)
        auth = AWSAuthV4(
            access_key=self.credentials.aws_access_key,
            secret_key=self.credentials.aws_secret_key,
            region=self.region
        )
        auth.access_token = self._access_token

        for attempt in range(retry_count):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_data,
                    auth=auth,
                    timeout=30
                )

                response.raise_for_status()

                return response.json()

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Rate limit
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Rate limited, retrying in {wait_time}s")
                    time.sleep(wait_time)
                    continue
                elif e.response.status_code == 403:  # Token expired
                    logger.info("Token expired, refreshing")
                    self.get_access_token(force_refresh=True)
                    headers = self._get_auth_headers()
                    continue
                else:
                    logger.error(f"SP-API request failed: {e}")
                    raise

            except Exception as e:
                logger.error(f"Request error (attempt {attempt + 1}): {e}")
                if attempt == retry_count - 1:
                    raise
                time.sleep(1)

        raise Exception(f"Request failed after {retry_count} attempts")

    # ========================================================================
    # CATALOG ITEMS API
    # ========================================================================

    def search_catalog(
        self,
        keywords: Optional[str] = None,
        identifiers: Optional[List[str]] = None,
        identifiers_type: str = "ASIN",
        marketplace_ids: Optional[List[str]] = None,
        included_data: Optional[List[str]] = None,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Search Amazon catalog for products.

        Args:
            keywords: Search keywords
            identifiers: List of ASINs, UPCs, EANs, etc.
            identifiers_type: ASIN, UPC, EAN, ISBN, etc.
            marketplace_ids: List of marketplace IDs
            included_data: Data to include (summaries, images, salesRanks, etc.)
            page_size: Results per page (max 20)

        Returns:
            Catalog search results

        Example:
            results = client.search_catalog(keywords="yoga mat")
        """

        params = {
            "marketplaceIds": marketplace_ids or [self.credentials.marketplace_id],
            "pageSize": min(page_size, 20)
        }

        if keywords:
            params["keywords"] = keywords

        if identifiers:
            params["identifiers"] = ",".join(identifiers)
            params["identifiersType"] = identifiers_type

        if included_data:
            params["includedData"] = ",".join(included_data)

        return self._request(
            method="GET",
            endpoint="/catalog/2022-04-01/items",
            api_type="catalog",
            params=params
        )

    def get_catalog_item(
        self,
        asin: str,
        marketplace_ids: Optional[List[str]] = None,
        included_data: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get detailed information for a specific ASIN.

        Args:
            asin: Amazon Standard Identification Number
            marketplace_ids: List of marketplace IDs
            included_data: Data to include

        Returns:
            Product details
        """

        params = {
            "marketplaceIds": marketplace_ids or [self.credentials.marketplace_id]
        }

        if included_data:
            params["includedData"] = ",".join(included_data)

        return self._request(
            method="GET",
            endpoint=f"/catalog/2022-04-01/items/{asin}",
            api_type="catalog",
            params=params
        )

    # ========================================================================
    # LISTINGS API
    # ========================================================================

    def get_listing(
        self,
        seller_sku: str,
        marketplace_ids: Optional[List[str]] = None,
        issue_locale: str = "en_US"
    ) -> Dict[str, Any]:
        """
        Get listing details for a seller SKU.

        Args:
            seller_sku: Your SKU
            marketplace_ids: List of marketplace IDs
            issue_locale: Locale for issue messages

        Returns:
            Listing details
        """

        params = {
            "marketplaceIds": marketplace_ids or [self.credentials.marketplace_id],
            "issueLocale": issue_locale
        }

        return self._request(
            method="GET",
            endpoint=f"/listings/2021-08-01/items/{self.credentials.marketplace_id}/{seller_sku}",
            api_type="listings",
            params=params
        )

    def create_or_update_listing(
        self,
        seller_sku: str,
        product_type: str,
        requirements: str,
        attributes: Dict[str, Any],
        marketplace_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create or update a product listing.

        Args:
            seller_sku: Your SKU
            product_type: Amazon product type (e.g., "LUGGAGE")
            requirements: "LISTING" or "LISTING_PRODUCT_ONLY"
            attributes: Product attributes
            marketplace_ids: List of marketplace IDs

        Returns:
            Submission response

        Example:
            response = client.create_or_update_listing(
                seller_sku="YOGA-MAT-001",
                product_type="SPORTING_GOODS",
                requirements="LISTING",
                attributes={
                    "condition_type": [{"value": "new_new", "marketplace_id": "ATVPDKIKX0DER"}],
                    "item_name": [{"value": "Premium Yoga Mat", "marketplace_id": "ATVPDKIKX0DER"}],
                    "brand": [{"value": "YogaPro", "marketplace_id": "ATVPDKIKX0DER"}],
                    "list_price": [{"value": 29.99, "currency": "USD", "marketplace_id": "ATVPDKIKX0DER"}],
                    # ... more attributes
                }
            )
        """

        marketplace_id = marketplace_ids[0] if marketplace_ids else self.credentials.marketplace_id

        body = {
            "productType": product_type,
            "requirements": requirements,
            "attributes": attributes
        }

        return self._request(
            method="PUT",
            endpoint=f"/listings/2021-08-01/items/{marketplace_id}/{seller_sku}",
            api_type="listings",
            json_data=body
        )

    def delete_listing(
        self,
        seller_sku: str,
        marketplace_ids: Optional[List[str]] = None,
        issue_locale: str = "en_US"
    ) -> Dict[str, Any]:
        """
        Delete a product listing.

        Args:
            seller_sku: Your SKU
            marketplace_ids: List of marketplace IDs
            issue_locale: Locale for issue messages

        Returns:
            Deletion response
        """

        marketplace_id = marketplace_ids[0] if marketplace_ids else self.credentials.marketplace_id

        params = {
            "marketplaceIds": marketplace_id,
            "issueLocale": issue_locale
        }

        return self._request(
            method="DELETE",
            endpoint=f"/listings/2021-08-01/items/{marketplace_id}/{seller_sku}",
            api_type="listings",
            params=params
        )

    # ========================================================================
    # ORDERS API
    # ========================================================================

    def get_orders(
        self,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
        last_updated_after: Optional[str] = None,
        order_statuses: Optional[List[str]] = None,
        fulfillment_channels: Optional[List[str]] = None,
        marketplace_ids: Optional[List[str]] = None,
        max_results: int = 100,
        next_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get orders matching filters.

        Args:
            created_after: ISO 8601 date (e.g., "2025-01-01T00:00:00Z")
            created_before: ISO 8601 date
            last_updated_after: ISO 8601 date
            order_statuses: ["Pending", "Unshipped", "PartiallyShipped", "Shipped", "Canceled"]
            fulfillment_channels: ["AFN" (FBA), "MFN" (FBM)]
            marketplace_ids: List of marketplace IDs
            max_results: Max results (1-100)
            next_token: Pagination token

        Returns:
            Orders list

        Example:
            orders = client.get_orders(
                created_after="2025-01-01T00:00:00Z",
                fulfillment_channels=["AFN"]
            )
        """

        params = {
            "MarketplaceIds": marketplace_ids or [self.credentials.marketplace_id],
            "MaxResultsPerPage": min(max_results, 100)
        }

        if created_after:
            params["CreatedAfter"] = created_after
        if created_before:
            params["CreatedBefore"] = created_before
        if last_updated_after:
            params["LastUpdatedAfter"] = last_updated_after
        if order_statuses:
            params["OrderStatuses"] = ",".join(order_statuses)
        if fulfillment_channels:
            params["FulfillmentChannels"] = ",".join(fulfillment_channels)
        if next_token:
            params["NextToken"] = next_token

        return self._request(
            method="GET",
            endpoint="/orders/v0/orders",
            api_type="orders",
            params=params
        )

    def get_order(self, order_id: str) -> Dict[str, Any]:
        """
        Get single order by ID.

        Args:
            order_id: Amazon order ID

        Returns:
            Order details
        """

        return self._request(
            method="GET",
            endpoint=f"/orders/v0/orders/{order_id}",
            api_type="orders"
        )

    def get_order_items(self, order_id: str) -> Dict[str, Any]:
        """
        Get line items for an order.

        Args:
            order_id: Amazon order ID

        Returns:
            Order items
        """

        return self._request(
            method="GET",
            endpoint=f"/orders/v0/orders/{order_id}/orderItems",
            api_type="orders"
        )

    # ========================================================================
    # FBA INVENTORY API
    # ========================================================================

    def get_inventory_summaries(
        self,
        granularity_type: str = "Marketplace",
        granularity_id: Optional[str] = None,
        marketplace_ids: Optional[List[str]] = None,
        details: bool = True,
        start_date_time: Optional[str] = None,
        seller_skus: Optional[List[str]] = None,
        next_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get FBA inventory summaries.

        Args:
            granularity_type: "Marketplace" or "ASIN"
            granularity_id: Marketplace or ASIN ID
            marketplace_ids: List of marketplace IDs
            details: Include details (reserved quantity, inbound, etc.)
            start_date_time: Filter by last updated date
            seller_skus: Filter by SKUs
            next_token: Pagination token

        Returns:
            Inventory summaries
        """

        params = {
            "granularityType": granularity_type,
            "marketplaceIds": marketplace_ids or [self.credentials.marketplace_id],
            "details": str(details).lower()
        }

        if granularity_id:
            params["granularityId"] = granularity_id
        if start_date_time:
            params["startDateTime"] = start_date_time
        if seller_skus:
            params["sellerSkus"] = ",".join(seller_skus)
        if next_token:
            params["nextToken"] = next_token

        return self._request(
            method="GET",
            endpoint="/fba/inventory/v1/summaries",
            api_type="inventory",
            params=params
        )

    # ========================================================================
    # FBA INBOUND API (Shipments)
    # ========================================================================

    def create_inbound_shipment_plan(
        self,
        ship_from_address: Dict[str, str],
        inbound_shipment_plan_request_items: List[Dict[str, Any]],
        label_prep_preference: str = "SELLER_LABEL",
        marketplace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create inbound shipment plan (first step for FBA shipments).

        Args:
            ship_from_address: Origin address
            inbound_shipment_plan_request_items: Items to ship
            label_prep_preference: "SELLER_LABEL" or "AMAZON_LABEL_ONLY"
            marketplace_id: Marketplace ID

        Returns:
            Shipment plan

        Example:
            plan = client.create_inbound_shipment_plan(
                ship_from_address={
                    "Name": "YogaPro Warehouse",
                    "AddressLine1": "123 Main St",
                    "City": "Los Angeles",
                    "StateOrProvinceCode": "CA",
                    "PostalCode": "90001",
                    "CountryCode": "US"
                },
                inbound_shipment_plan_request_items=[
                    {
                        "SellerSKU": "YOGA-MAT-001",
                        "Quantity": 100,
                        "ASIN": "B08XYZ123",
                        "Condition": "NewItem"
                    }
                ]
            )
        """

        body = {
            "ShipFromAddress": ship_from_address,
            "InboundShipmentPlanRequestItems": inbound_shipment_plan_request_items,
            "LabelPrepPreference": label_prep_preference,
            "ShipToCountryCode": "US"  # FBA country
        }

        return self._request(
            method="POST",
            endpoint="/fba/inbound/v0/plans",
            api_type="shipments",
            json_data=body
        )

    def get_shipment(
        self,
        shipment_id: str,
        marketplace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get inbound shipment details.

        Args:
            shipment_id: FBA shipment ID
            marketplace_id: Marketplace ID

        Returns:
            Shipment details
        """

        params = {
            "MarketplaceId": marketplace_id or self.credentials.marketplace_id
        }

        return self._request(
            method="GET",
            endpoint=f"/fba/inbound/v0/shipments/{shipment_id}",
            api_type="shipments",
            params=params
        )

    # ========================================================================
    # PRODUCT FEES API
    # ========================================================================

    def get_product_fees_estimate(
        self,
        asin: str,
        price: float,
        currency: str = "USD",
        is_fba: bool = True,
        marketplace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Estimate fees for a product.

        Args:
            asin: Product ASIN
            price: Selling price
            currency: Currency code
            is_fba: FBA or FBM
            marketplace_id: Marketplace ID

        Returns:
            Fee breakdown (fulfillment, referral, storage)

        Example:
            fees = client.get_product_fees_estimate(
                asin="B08XYZ123",
                price=29.99,
                is_fba=True
            )
        """

        body = {
            "FeesEstimateRequest": {
                "MarketplaceId": marketplace_id or self.credentials.marketplace_id,
                "IsAmazonFulfilled": is_fba,
                "PriceToEstimateFees": {
                    "ListingPrice": {
                        "Amount": price,
                        "CurrencyCode": currency
                    }
                },
                "Identifier": asin,
                "IdType": "ASIN",
                "IdValue": asin
            }
        }

        return self._request(
            method="POST",
            endpoint=f"/products/fees/v0/items/{asin}/feesEstimate",
            api_type="catalog",
            json_data=body
        )

    # ========================================================================
    # PRICING API
    # ========================================================================

    def get_competitive_pricing(
        self,
        asin: str,
        marketplace_id: Optional[str] = None,
        item_type: str = "Asin"
    ) -> Dict[str, Any]:
        """
        Get competitive pricing for a product.

        Args:
            asin: Product ASIN
            marketplace_id: Marketplace ID
            item_type: "Asin" or "Sku"

        Returns:
            Competitive pricing data
        """

        params = {
            "MarketplaceId": marketplace_id or self.credentials.marketplace_id,
            "ItemType": item_type,
            "Asins": asin
        }

        return self._request(
            method="GET",
            endpoint="/products/pricing/v0/competitivePrice",
            api_type="catalog",
            params=params
        )

    # ========================================================================
    # REPORTS API
    # ========================================================================

    def create_report(
        self,
        report_type: str,
        marketplace_ids: Optional[List[str]] = None,
        data_start_time: Optional[str] = None,
        data_end_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Request a report.

        Args:
            report_type: Report type (e.g., "GET_FLAT_FILE_OPEN_LISTINGS_DATA")
            marketplace_ids: List of marketplace IDs
            data_start_time: Start date (ISO 8601)
            data_end_time: End date (ISO 8601)

        Returns:
            Report request details

        Common report types:
        - GET_FLAT_FILE_OPEN_LISTINGS_DATA
        - GET_MERCHANT_LISTINGS_ALL_DATA
        - GET_FBA_FULFILLMENT_CURRENT_INVENTORY_DATA
        - GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA
        """

        body = {
            "reportType": report_type,
            "marketplaceIds": marketplace_ids or [self.credentials.marketplace_id]
        }

        if data_start_time:
            body["dataStartTime"] = data_start_time
        if data_end_time:
            body["dataEndTime"] = data_end_time

        return self._request(
            method="POST",
            endpoint="/reports/2021-06-30/reports",
            api_type="catalog",
            json_data=body
        )

    def get_report(self, report_id: str) -> Dict[str, Any]:
        """
        Get report status.

        Args:
            report_id: Report ID from create_report

        Returns:
            Report status and document ID
        """

        return self._request(
            method="GET",
            endpoint=f"/reports/2021-06-30/reports/{report_id}",
            api_type="catalog"
        )

    def get_report_document(self, report_document_id: str) -> Dict[str, Any]:
        """
        Get report document download URL.

        Args:
            report_document_id: Document ID from get_report

        Returns:
            Download URL
        """

        return self._request(
            method="GET",
            endpoint=f"/reports/2021-06-30/documents/{report_document_id}",
            api_type="catalog"
        )

    # ========================================================================
    # HEALTH CHECK
    # ========================================================================

    def test_connection(self) -> bool:
        """
        Test SP-API connection and authentication.

        Returns:
            True if connection successful
        """

        try:
            # Try to get access token
            self.get_access_token()

            # Try simple API call (get catalog)
            result = self.search_catalog(keywords="test", page_size=1)

            logger.info("✅ Amazon SP-API connection successful")
            return True

        except Exception as e:
            logger.error(f"❌ Amazon SP-API connection failed: {e}")
            return False
