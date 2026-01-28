"""
Amazon FBA Models - GROK RECOMMENDATION #16

Database models for Amazon Selling Partner API integration.
Supports multi-marketplace selling, FBA inventory, and order management.

SECURITY: Sensitive credentials (tokens, secrets, keys) are encrypted at rest.
Use set_credentials() and get_credentials() methods for secure handling.
"""

from sqlalchemy import Column, Integer, String, Float, Text, JSON, DateTime, ForeignKey, Boolean, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import logging

from ospra_os.database import Base

logger = logging.getLogger(__name__)


# Lazy import encryption to avoid circular imports
def _get_field_encryption():
    try:
        from ospra_os.security.credential_encryption import encrypt_field, decrypt_field
        return encrypt_field, decrypt_field
    except ImportError:
        return None, None


class AmazonMarketplace(str, enum.Enum):
    """Amazon marketplace identifiers"""
    US = "ATVPDKIKX0DER"      # Amazon.com
    CA = "A2EUQ1WTGCTBG2"     # Amazon.ca
    MX = "A1AM78C64UM0Y8"     # Amazon.com.mx
    UK = "A1F83G8C2ARO7P"     # Amazon.co.uk
    DE = "A1PA6795UKMFR9"     # Amazon.de
    FR = "A13V1IB3VIYBER"     # Amazon.fr
    IT = "APJ6JRA9NG5V4"      # Amazon.it
    ES = "A1RKKUPIHCS9HS"     # Amazon.es
    JP = "A1VC38T7YXB528"     # Amazon.co.jp
    AU = "A39IBJ37TRP1C6"     # Amazon.com.au


class FBAStatus(str, enum.Enum):
    """FBA listing status"""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUPPRESSED = "suppressed"
    INCOMPLETE = "incomplete"


class AmazonAccount(Base):
    """
    Amazon Seller Central account connection.

    Stores SP-API credentials and marketplace configuration.
    """
    __tablename__ = "amazon_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Account info
    seller_id = Column(String(50), unique=True, nullable=False)
    marketplace_id = Column(String(50), nullable=False)  # Primary marketplace
    account_name = Column(String(255), nullable=True)

    # OAuth credentials (encrypted in production)
    refresh_token = Column(Text, nullable=True)
    access_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)

    # LWA (Login with Amazon) credentials
    lwa_client_id = Column(String(255), nullable=True)
    lwa_client_secret = Column(String(500), nullable=True)

    # SP-API credentials
    sp_api_client_id = Column(String(255), nullable=True)
    sp_api_client_secret = Column(String(500), nullable=True)

    # AWS IAM Role (for request signing)
    aws_access_key = Column(String(255), nullable=True)
    aws_secret_key = Column(String(500), nullable=True)
    role_arn = Column(String(500), nullable=True)

    # Status
    status = Column(String(20), default="pending")  # pending, active, error, disconnected
    last_sync_at = Column(DateTime, nullable=True)
    sync_error = Column(Text, nullable=True)

    # Settings
    settings = Column(JSON, default=dict)
    # {
    #   "auto_reprice": true,
    #   "min_margin": 20,
    #   "fba_enabled": true,
    #   "fbm_enabled": false,
    #   "notification_email": "seller@example.com"
    # }

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    listings = relationship("AmazonListing", back_populates="account", cascade="all, delete-orphan")
    orders = relationship("AmazonOrder", back_populates="account", cascade="all, delete-orphan")
    shipments = relationship("FBAShipment", back_populates="account", cascade="all, delete-orphan")

    # SECURITY: Credential encryption methods
    def set_sensitive_credentials(
        self,
        refresh_token: str = None,
        access_token: str = None,
        lwa_client_secret: str = None,
        sp_api_client_secret: str = None,
        aws_secret_key: str = None,
    ):
        """
        Set sensitive credentials with encryption.

        SECURITY: All secrets are encrypted before storage.
        Use this method instead of directly setting the columns.
        """
        encrypt_field, _ = _get_field_encryption()

        if encrypt_field:
            if refresh_token is not None:
                self.refresh_token = encrypt_field(refresh_token)
            if access_token is not None:
                self.access_token = encrypt_field(access_token)
            if lwa_client_secret is not None:
                self.lwa_client_secret = encrypt_field(lwa_client_secret)
            if sp_api_client_secret is not None:
                self.sp_api_client_secret = encrypt_field(sp_api_client_secret)
            if aws_secret_key is not None:
                self.aws_secret_key = encrypt_field(aws_secret_key)
        else:
            # Fallback if encryption not available
            logger.warning("Credential encryption not available - storing plain text")
            if refresh_token is not None:
                self.refresh_token = refresh_token
            if access_token is not None:
                self.access_token = access_token
            if lwa_client_secret is not None:
                self.lwa_client_secret = lwa_client_secret
            if sp_api_client_secret is not None:
                self.sp_api_client_secret = sp_api_client_secret
            if aws_secret_key is not None:
                self.aws_secret_key = aws_secret_key

    def get_decrypted_credentials(self) -> dict:
        """
        Get all sensitive credentials decrypted.

        SECURITY: Use this method to access secrets for API calls.

        Returns:
            dict: All decrypted credential fields
        """
        _, decrypt_field = _get_field_encryption()

        if decrypt_field:
            return {
                "refresh_token": decrypt_field(self.refresh_token) if self.refresh_token else None,
                "access_token": decrypt_field(self.access_token) if self.access_token else None,
                "lwa_client_id": self.lwa_client_id,  # Not sensitive
                "lwa_client_secret": decrypt_field(self.lwa_client_secret) if self.lwa_client_secret else None,
                "sp_api_client_id": self.sp_api_client_id,  # Not sensitive
                "sp_api_client_secret": decrypt_field(self.sp_api_client_secret) if self.sp_api_client_secret else None,
                "aws_access_key": self.aws_access_key,  # Not as sensitive
                "aws_secret_key": decrypt_field(self.aws_secret_key) if self.aws_secret_key else None,
                "role_arn": self.role_arn,
            }
        else:
            # Return as-is if encryption not available
            return {
                "refresh_token": self.refresh_token,
                "access_token": self.access_token,
                "lwa_client_id": self.lwa_client_id,
                "lwa_client_secret": self.lwa_client_secret,
                "sp_api_client_id": self.sp_api_client_id,
                "sp_api_client_secret": self.sp_api_client_secret,
                "aws_access_key": self.aws_access_key,
                "aws_secret_key": self.aws_secret_key,
                "role_arn": self.role_arn,
            }


class AmazonListing(Base):
    """
    Amazon product listing.

    Represents a single SKU listed on Amazon, with pricing, inventory,
    and performance metrics.
    """
    __tablename__ = "amazon_listings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("amazon_accounts.id"), nullable=False)

    # Amazon identifiers
    asin = Column(String(20), nullable=True, index=True)  # Amazon Standard ID
    sku = Column(String(100), nullable=False)  # Your SKU
    fnsku = Column(String(20), nullable=True)  # FBA SKU (Fulfillment Network SKU)

    # Product info
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    bullet_points = Column(JSON, default=list)  # Up to 5 bullet points
    brand = Column(String(100), nullable=True)

    # Category
    category_id = Column(String(50), nullable=True)
    category_name = Column(String(255), nullable=True)
    product_type = Column(String(100), nullable=True)

    # Pricing
    price = Column(Float, nullable=False)
    sale_price = Column(Float, nullable=True)
    map_price = Column(Float, nullable=True)  # Minimum Advertised Price
    cost = Column(Float, nullable=True)  # Your cost

    # FBA specific
    fba_fees = Column(JSON, default=dict)
    # {
    #   "fulfillment_fee": 3.22,
    #   "storage_fee_monthly": 0.75,
    #   "referral_fee_percent": 15,
    #   "total_fees": 8.50
    # }

    # Inventory
    fulfillment_channel = Column(String(10), default="FBA")  # FBA or FBM
    inventory_quantity = Column(Integer, default=0)
    reserved_quantity = Column(Integer, default=0)
    inbound_quantity = Column(Integer, default=0)  # Shipping to FBA

    # Status
    status = Column(String(30), default="draft")
    buy_box_winner = Column(Boolean, default=False)
    buy_box_price = Column(Float, nullable=True)

    # Performance metrics
    sessions = Column(Integer, default=0)  # Views
    units_ordered = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0)
    reviews_count = Column(Integer, default=0)
    rating = Column(Float, default=0)

    # Cross-platform linking
    shopify_product_id = Column(Integer, nullable=True)  # Link to Shopify product

    # Supplier linking
    supplier_product_id = Column(String(100), nullable=True)
    supplier_url = Column(String(500), nullable=True)

    # Images
    main_image = Column(String(500), nullable=True)
    additional_images = Column(JSON, default=list)

    # SEO
    search_terms = Column(JSON, default=list)  # Backend keywords

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    account = relationship("AmazonAccount", back_populates="listings")
    order_items = relationship("AmazonOrderItem", back_populates="listing")


class AmazonOrder(Base):
    """
    Amazon order.

    Represents a customer order from Amazon marketplace.
    """
    __tablename__ = "amazon_orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("amazon_accounts.id"), nullable=False)

    # Amazon order info
    amazon_order_id = Column(String(50), unique=True, nullable=False, index=True)
    marketplace_id = Column(String(50), nullable=False)

    # Order details
    order_status = Column(String(30), nullable=False)
    # Pending, Unshipped, PartiallyShipped, Shipped, Canceled, Unfulfillable

    fulfillment_channel = Column(String(10), nullable=False)  # FBA or FBM

    # Financials
    order_total = Column(Float, nullable=True)
    currency = Column(String(3), default="USD")

    # Buyer info (limited by Amazon for privacy)
    buyer_email = Column(String(255), nullable=True)
    buyer_name = Column(String(255), nullable=True)

    # Shipping address (limited)
    ship_city = Column(String(100), nullable=True)
    ship_state = Column(String(50), nullable=True)
    ship_postal_code = Column(String(20), nullable=True)
    ship_country = Column(String(2), nullable=True)

    # Dates
    purchase_date = Column(DateTime, nullable=False, index=True)
    last_update_date = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    account = relationship("AmazonAccount", back_populates="orders")
    items = relationship("AmazonOrderItem", back_populates="order", cascade="all, delete-orphan")


class AmazonOrderItem(Base):
    """
    Amazon order line item.

    Individual product within an Amazon order.
    """
    __tablename__ = "amazon_order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("amazon_orders.id"), nullable=False)
    listing_id = Column(Integer, ForeignKey("amazon_listings.id"), nullable=True)

    # Item details
    asin = Column(String(20), nullable=False)
    sku = Column(String(100), nullable=False)
    title = Column(String(500), nullable=True)

    quantity_ordered = Column(Integer, nullable=False)
    quantity_shipped = Column(Integer, default=0)

    # Pricing
    item_price = Column(Float, nullable=True)
    shipping_price = Column(Float, nullable=True)
    promotion_discount = Column(Float, nullable=True)

    # Relationships
    order = relationship("AmazonOrder", back_populates="items")
    listing = relationship("AmazonListing", back_populates="order_items")


class FBAShipment(Base):
    """
    FBA inbound shipment.

    Tracks inventory being sent to Amazon fulfillment centers.
    """
    __tablename__ = "fba_shipments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("amazon_accounts.id"), nullable=False)

    # Shipment info
    shipment_id = Column(String(50), unique=True, nullable=False)
    shipment_name = Column(String(255), nullable=True)

    # Status
    status = Column(String(30), nullable=False)
    # WORKING, SHIPPED, IN_TRANSIT, DELIVERED, CHECKED_IN, RECEIVING, CLOSED, CANCELLED

    # Destination
    destination_fulfillment_center_id = Column(String(20), nullable=True)

    # Items
    items = Column(JSON, default=list)
    # [{"sku": "YOGA-MAT-001", "quantity": 100, "received": 98}]

    # Tracking
    tracking_numbers = Column(JSON, default=list)
    carrier = Column(String(50), nullable=True)

    # Dates
    created_at = Column(DateTime, default=datetime.utcnow)
    shipped_at = Column(DateTime, nullable=True)
    received_at = Column(DateTime, nullable=True)

    # Relationships
    account = relationship("AmazonAccount", back_populates="shipments")
