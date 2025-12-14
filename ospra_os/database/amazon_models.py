"""
Amazon FBA Models - GROK RECOMMENDATION #16

Database models for Amazon Selling Partner API integration.
Supports multi-marketplace selling, FBA inventory, and order management.
"""

from sqlalchemy import Column, Integer, String, Float, Text, JSON, DateTime, ForeignKey, Boolean, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from ospra_os.database.multi_store_models import Base


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
