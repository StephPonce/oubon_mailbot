"""
Platform Factory

Centralized factory for creating platform adapter instances.
Simplifies platform adapter instantiation and provides metadata about supported platforms.

Author: OspraOS
Date: November 2025
"""

from typing import Dict, List, Optional, Type, Any
import logging

from ospra_os.platforms.base import (
    PlatformAdapter,
    AuthenticationError,
    validate_platform_name
)
from ospra_os.platforms.shopify import ShopifyAdapter
from ospra_os.platforms.amazon import AmazonAdapter
from ospra_os.platforms.woocommerce import WooCommerceAdapter

logger = logging.getLogger(__name__)


class PlatformFactory:
    """
    Factory for creating platform adapter instances.

    Provides a centralized registry of all supported platforms and
    methods for instantiating adapters with proper credentials.

    Example:
        >>> from ospra_os.platforms.factory import PlatformFactory
        >>>
        >>> credentials = {
        ...     "store_domain": "mystore.myshopify.com",
        ...     "admin_api_token": "shpat_xxxxx"
        ... }
        >>>
        >>> adapter = PlatformFactory.get_adapter("shopify", credentials)
        >>> result = await adapter.test_connection()
    """

    # Registry of all available platform adapters
    _adapters: Dict[str, Type[PlatformAdapter]] = {
        "shopify": ShopifyAdapter,
        "amazon": AmazonAdapter,
        "woocommerce": WooCommerceAdapter
    }

    # Platform metadata
    _platform_metadata = {
        "shopify": {
            "name": "shopify",
            "display_name": "Shopify",
            "description": "Shopify hosted e-commerce platform",
            "complexity": "medium",
            "setup_time_minutes": 5,
            "credentials_count": 2,
            "features": {
                "product_creation": True,
                "product_updates": True,
                "product_deletion": True,
                "inventory_management": True,
                "order_management": True,
                "multi_location": True,
                "webhooks": True
            },
            "limitations": [],
            "api_version": "2024-01",
            "documentation_url": "https://shopify.dev/docs/api/admin-rest"
        },
        "amazon": {
            "name": "amazon",
            "display_name": "Amazon Seller Partner",
            "description": "Amazon marketplace via SP-API",
            "complexity": "high",
            "setup_time_minutes": 30,
            "credentials_count": 7,
            "features": {
                "product_creation": False,  # MVP - deferred
                "product_updates": False,   # MVP - limited
                "product_deletion": False,  # MVP - archive only
                "inventory_management": False,  # MVP - deferred
                "order_management": True,
                "multi_location": False,
                "webhooks": False
            },
            "limitations": [
                "Product creation requires brand registry and UPC codes",
                "Inventory management differs by fulfillment method (FBA/FBM)",
                "Product listing requires Reports API (async)"
            ],
            "api_version": "2021-06-30",
            "documentation_url": "https://developer-docs.amazon.com/sp-api/"
        },
        "woocommerce": {
            "name": "woocommerce",
            "display_name": "WooCommerce",
            "description": "WordPress WooCommerce self-hosted",
            "complexity": "low",
            "setup_time_minutes": 2,
            "credentials_count": 3,
            "features": {
                "product_creation": True,
                "product_updates": True,
                "product_deletion": True,
                "inventory_management": True,
                "order_management": True,
                "multi_location": False,
                "webhooks": True
            },
            "limitations": [],
            "api_version": "wc/v3",
            "documentation_url": "https://woocommerce.github.io/woocommerce-rest-api-docs/"
        }
    }

    # Credential definitions for each platform
    _credential_schemas = {
        "shopify": [
            {
                "field": "store_domain",
                "label": "Store Domain",
                "type": "text",
                "required": True,
                "placeholder": "mystore.myshopify.com",
                "help_text": "Your Shopify store domain (without https://)",
                "validation": r"^[a-z0-9-]+\.myshopify\.com$"
            },
            {
                "field": "admin_api_token",
                "label": "Admin API Access Token",
                "type": "password",
                "required": True,
                "placeholder": "shpat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "help_text": "Admin API access token from Shopify settings",
                "validation": r"^shpat_[a-f0-9]{32}$"
            },
            {
                "field": "api_version",
                "label": "API Version",
                "type": "text",
                "required": False,
                "placeholder": "2024-01",
                "help_text": "Shopify API version (defaults to 2024-01)",
                "default": "2024-01"
            }
        ],
        "amazon": [
            {
                "field": "marketplace_id",
                "label": "Marketplace ID",
                "type": "select",
                "required": True,
                "options": [
                    {"value": "ATVPDKIKX0DER", "label": "United States"},
                    {"value": "A2EUQ1WTGCTBG2", "label": "Canada"},
                    {"value": "A1AM78C64UM0Y8", "label": "Mexico"},
                    {"value": "A1PA6795UKMFR9", "label": "Germany"},
                    {"value": "A1RKKUPIHCS9HS", "label": "Spain"},
                    {"value": "A13V1IB3VIYZZH", "label": "France"},
                    {"value": "A1F83G8C2ARO7P", "label": "United Kingdom"},
                    {"value": "APJ6JRA9NG5V4", "label": "Italy"},
                    {"value": "A1VC38T7YXB528", "label": "Japan"},
                    {"value": "A39IBJ37TRP1C6", "label": "Australia"}
                ],
                "help_text": "Amazon marketplace where you sell"
            },
            {
                "field": "seller_id",
                "label": "Seller ID",
                "type": "text",
                "required": True,
                "placeholder": "A1234567890123",
                "help_text": "Your Amazon Seller ID"
            },
            {
                "field": "refresh_token",
                "label": "Refresh Token",
                "type": "password",
                "required": True,
                "placeholder": "Atzr|IwEBIA...",
                "help_text": "LWA OAuth refresh token"
            },
            {
                "field": "client_id",
                "label": "LWA Client ID",
                "type": "text",
                "required": True,
                "placeholder": "amzn1.application-oa2-client...",
                "help_text": "Login with Amazon application client ID"
            },
            {
                "field": "client_secret",
                "label": "LWA Client Secret",
                "type": "password",
                "required": True,
                "placeholder": "amzn1.oa2-cs.v1...",
                "help_text": "Login with Amazon application secret"
            },
            {
                "field": "aws_access_key",
                "label": "AWS Access Key",
                "type": "text",
                "required": True,
                "placeholder": "AKIA...",
                "help_text": "AWS IAM user access key"
            },
            {
                "field": "aws_secret_key",
                "label": "AWS Secret Key",
                "type": "password",
                "required": True,
                "help_text": "AWS IAM user secret key"
            }
        ],
        "woocommerce": [
            {
                "field": "store_url",
                "label": "Store URL",
                "type": "text",
                "required": True,
                "placeholder": "https://mystore.com",
                "help_text": "Your WooCommerce store URL (with https://)",
                "validation": r"^https?://.*"
            },
            {
                "field": "consumer_key",
                "label": "Consumer Key",
                "type": "text",
                "required": True,
                "placeholder": "ck_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "help_text": "WooCommerce REST API consumer key",
                "validation": r"^ck_[a-f0-9]{40}$"
            },
            {
                "field": "consumer_secret",
                "label": "Consumer Secret",
                "type": "password",
                "required": True,
                "placeholder": "cs_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "help_text": "WooCommerce REST API consumer secret",
                "validation": r"^cs_[a-f0-9]{40}$"
            }
        ]
    }

    @classmethod
    def get_adapter(cls, platform: str, credentials: dict) -> PlatformAdapter:
        """
        Get platform adapter instance for specified platform.

        Args:
            platform: Platform name ("shopify", "amazon", "woocommerce")
            credentials: Dictionary with platform-specific credentials

        Returns:
            Instantiated platform adapter

        Raises:
            ValueError: If platform not supported
            AuthenticationError: If credentials invalid

        Example:
            >>> adapter = PlatformFactory.get_adapter("shopify", {
            ...     "store_domain": "mystore.myshopify.com",
            ...     "admin_api_token": "shpat_xxxxx"
            ... })
        """
        platform = platform.lower()

        if platform not in cls._adapters:
            available = ", ".join(cls._adapters.keys())
            raise ValueError(
                f"Unknown platform: '{platform}'. "
                f"Available platforms: {available}"
            )

        adapter_class = cls._adapters[platform]

        try:
            adapter = adapter_class(credentials)
            logger.info(f"Created {platform} adapter instance")
            return adapter
        except AuthenticationError as e:
            logger.error(f"Failed to create {platform} adapter: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating {platform} adapter: {e}")
            raise

    @classmethod
    def get_available_platforms(cls) -> List[Dict[str, Any]]:
        """
        Get list of all supported platforms with metadata.

        Returns:
            List of platform information dictionaries

        Example:
            >>> platforms = PlatformFactory.get_available_platforms()
            >>> for platform in platforms:
            ...     print(f"{platform['display_name']}: {platform['complexity']}")
        """
        platforms = []

        for name in cls._adapters.keys():
            metadata = cls._platform_metadata.get(name, {})
            platforms.append({
                "name": name,
                "display_name": metadata.get("display_name", name.title()),
                "description": metadata.get("description", ""),
                "complexity": metadata.get("complexity", "unknown"),
                "setup_time_minutes": metadata.get("setup_time_minutes", 0),
                "credentials_count": metadata.get("credentials_count", 0),
                "features": metadata.get("features", {}),
                "limitations": metadata.get("limitations", []),
                "api_version": metadata.get("api_version", ""),
                "documentation_url": metadata.get("documentation_url", "")
            })

        return platforms

    @classmethod
    def validate_credentials(cls, platform: str, credentials: dict) -> dict:
        """
        Validate credential structure for specified platform.

        Args:
            platform: Platform name
            credentials: Credentials dictionary to validate

        Returns:
            {
                "valid": True/False,
                "missing_fields": [...],
                "errors": [...]
            }

        Example:
            >>> result = PlatformFactory.validate_credentials("shopify", {
            ...     "store_domain": "mystore.myshopify.com"
            ... })
            >>> if not result["valid"]:
            ...     print(f"Missing: {result['missing_fields']}")
        """
        platform = platform.lower()

        if platform not in cls._credential_schemas:
            return {
                "valid": False,
                "missing_fields": [],
                "errors": [f"Unknown platform: {platform}"]
            }

        schema = cls._credential_schemas[platform]
        missing_fields = []
        errors = []

        # Check required fields
        for field_def in schema:
            if field_def["required"]:
                field_name = field_def["field"]
                if field_name not in credentials or not credentials[field_name]:
                    missing_fields.append({
                        "field": field_name,
                        "label": field_def["label"]
                    })

        # Basic validation (can be enhanced with regex)
        for field_def in schema:
            field_name = field_def["field"]
            if field_name in credentials and credentials[field_name]:
                # Type validation could go here
                pass

        is_valid = len(missing_fields) == 0 and len(errors) == 0

        return {
            "valid": is_valid,
            "missing_fields": missing_fields,
            "errors": errors
        }

    @classmethod
    def get_required_credentials(cls, platform: str) -> List[Dict[str, Any]]:
        """
        Get list of required credential fields for specified platform.

        Args:
            platform: Platform name

        Returns:
            List of credential field definitions

        Example:
            >>> fields = PlatformFactory.get_required_credentials("shopify")
            >>> for field in fields:
            ...     print(f"{field['label']}: {field['help_text']}")
        """
        platform = platform.lower()

        if platform not in cls._credential_schemas:
            raise ValueError(f"Unknown platform: {platform}")

        return cls._credential_schemas[platform]

    @classmethod
    def get_platform_metadata(cls, platform: str) -> Dict[str, Any]:
        """
        Get detailed metadata for specified platform.

        Args:
            platform: Platform name

        Returns:
            Platform metadata dictionary

        Example:
            >>> metadata = PlatformFactory.get_platform_metadata("shopify")
            >>> print(f"Complexity: {metadata['complexity']}")
            >>> print(f"Features: {metadata['features']}")
        """
        platform = platform.lower()

        if platform not in cls._platform_metadata:
            raise ValueError(f"Unknown platform: {platform}")

        return cls._platform_metadata[platform]

    @classmethod
    def register_adapter(
        cls,
        name: str,
        adapter_class: Type[PlatformAdapter],
        metadata: Optional[Dict[str, Any]] = None,
        credential_schema: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Register a new platform adapter (for extensions).

        Args:
            name: Platform name
            adapter_class: Adapter class (must inherit from PlatformAdapter)
            metadata: Optional platform metadata
            credential_schema: Optional credential field definitions

        Example:
            >>> class MyPlatformAdapter(PlatformAdapter):
            ...     pass
            >>>
            >>> PlatformFactory.register_adapter(
            ...     "myplatform",
            ...     MyPlatformAdapter,
            ...     metadata={"display_name": "My Platform", ...}
            ... )
        """
        name = name.lower()

        if not issubclass(adapter_class, PlatformAdapter):
            raise ValueError(
                f"Adapter class must inherit from PlatformAdapter"
            )

        cls._adapters[name] = adapter_class

        if metadata:
            cls._platform_metadata[name] = metadata

        if credential_schema:
            cls._credential_schemas[name] = credential_schema

        logger.info(f"Registered platform adapter: {name}")

    @classmethod
    def list_adapters(cls) -> List[str]:
        """
        Get list of all registered platform names.

        Returns:
            List of platform names

        Example:
            >>> platforms = PlatformFactory.list_adapters()
            >>> print(f"Supported: {', '.join(platforms)}")
        """
        return list(cls._adapters.keys())

    @classmethod
    def get_adapter_class(cls, platform: str) -> Type[PlatformAdapter]:
        """
        Get adapter class without instantiating.

        Args:
            platform: Platform name

        Returns:
            Adapter class

        Example:
            >>> AdapterClass = PlatformFactory.get_adapter_class("shopify")
            >>> adapter = AdapterClass(credentials)
        """
        platform = platform.lower()

        if platform not in cls._adapters:
            raise ValueError(f"Unknown platform: {platform}")

        return cls._adapters[platform]

    @classmethod
    def compare_platforms(cls) -> Dict[str, Any]:
        """
        Generate comparison matrix of all platforms.

        Returns:
            Comparison data with features, complexity, etc.

        Example:
            >>> comparison = PlatformFactory.compare_platforms()
            >>> print(comparison["features_matrix"])
        """
        platforms = cls.get_available_platforms()

        # Build comparison matrix
        comparison = {
            "platforms": [p["name"] for p in platforms],
            "complexity": {p["name"]: p["complexity"] for p in platforms},
            "credentials_count": {p["name"]: p["credentials_count"] for p in platforms},
            "setup_time": {p["name"]: p["setup_time_minutes"] for p in platforms},
            "features_matrix": {}
        }

        # Compare features
        all_features = set()
        for platform in platforms:
            all_features.update(platform["features"].keys())

        for feature in all_features:
            comparison["features_matrix"][feature] = {}
            for platform in platforms:
                has_feature = platform["features"].get(feature, False)
                comparison["features_matrix"][feature][platform["name"]] = has_feature

        return comparison
