"""
Amazon Service Layer - GROK RECOMMENDATION #16

Business logic for Amazon FBA operations.

Manages:
- Account connections (OAuth flow, credential storage)
- Product research (search catalog, analyze profitability)
- Listing management (create, update, sync)
- Order synchronization
- FBA inventory tracking
- Inbound shipments

Uses:
- AmazonSPAPIClient for API calls
- Database models for persistence
- Cross-platform linking (Shopify <-> Amazon)
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from ospra_os.integrations.amazon_client import AmazonSPAPIClient, AmazonCredentials
from ospra_os.database.amazon_models import (
    AmazonAccount,
    AmazonListing,
    AmazonOrder,
    AmazonOrderItem,
    FBAShipment,
    FBAStatus
)

logger = logging.getLogger(__name__)


class AmazonService:
    """
    Service layer for Amazon FBA operations.

    Provides high-level business logic for:
    - Account management
    - Product research
    - Listing management
    - Order synchronization
    - Inventory tracking
    - Profitability analysis

    Example:
        service = AmazonService(db)

        # Connect account
        account = service.connect_account(
            user_id=1,
            seller_id="A1B2C3D4E5F6G7",
            credentials={...}
        )

        # Research products
        results = service.research_products(
            account_id=account.id,
            keywords="yoga mat"
        )

        # Create listing
        listing = service.create_listing(
            account_id=account.id,
            product_data={...}
        )
    """

    def __init__(self, db: Session):
        self.db = db
        logger.info("AmazonService initialized")

    def _get_client(self, account: AmazonAccount) -> AmazonSPAPIClient:
        """
        Create SP-API client for an account.

        Args:
            account: AmazonAccount with credentials

        Returns:
            Configured AmazonSPAPIClient
        """

        credentials = AmazonCredentials(
            lwa_client_id=account.lwa_client_id,
            lwa_client_secret=account.lwa_client_secret,
            refresh_token=account.refresh_token,
            aws_access_key=account.aws_access_key,
            aws_secret_key=account.aws_secret_key,
            role_arn=account.role_arn,
            marketplace_id=account.marketplace_id
        )

        # Determine region from marketplace
        region = "us-east-1"  # Default US
        if account.marketplace_id.startswith("A1") and "UK" in account.marketplace_id:
            region = "eu-west-1"
        elif account.marketplace_id == "A1VC38T7YXB528":  # Japan
            region = "us-west-2"

        return AmazonSPAPIClient(credentials, region=region)

    # ========================================================================
    # ACCOUNT MANAGEMENT
    # ========================================================================

    def connect_account(
        self,
        user_id: int,
        seller_id: str,
        marketplace_id: str,
        lwa_client_id: str,
        lwa_client_secret: str,
        refresh_token: str,
        aws_access_key: str,
        aws_secret_key: str,
        role_arn: Optional[str] = None,
        account_name: Optional[str] = None
    ) -> AmazonAccount:
        """
        Connect Amazon Seller Central account.

        Args:
            user_id: User ID
            seller_id: Amazon Seller ID
            marketplace_id: Primary marketplace
            lwa_client_id: LWA OAuth client ID
            lwa_client_secret: LWA OAuth client secret
            refresh_token: LWA refresh token
            aws_access_key: AWS access key
            aws_secret_key: AWS secret key
            role_arn: AWS IAM role ARN (optional)
            account_name: Friendly name for account

        Returns:
            Created AmazonAccount

        Raises:
            Exception if connection test fails
        """

        logger.info(f"Connecting Amazon account for user {user_id}, seller {seller_id}")

        # Create account record
        account = AmazonAccount(
            user_id=user_id,
            seller_id=seller_id,
            marketplace_id=marketplace_id,
            account_name=account_name or f"Amazon - {seller_id}",
            lwa_client_id=lwa_client_id,
            lwa_client_secret=lwa_client_secret,
            refresh_token=refresh_token,
            aws_access_key=aws_access_key,
            aws_secret_key=aws_secret_key,
            role_arn=role_arn,
            status="pending"
        )

        # Test connection
        try:
            client = self._get_client(account)
            if client.test_connection():
                account.status = "active"
                account.last_sync_at = datetime.utcnow()
                logger.info("✅ Amazon account connected successfully")
            else:
                account.status = "error"
                account.sync_error = "Connection test failed"
                logger.error("❌ Amazon connection test failed")

        except Exception as e:
            account.status = "error"
            account.sync_error = str(e)
            logger.error(f"❌ Amazon connection error: {e}")

        # Save to database
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)

        return account

    def disconnect_account(self, account_id: int) -> bool:
        """
        Disconnect Amazon account.

        Args:
            account_id: Amazon account ID

        Returns:
            True if successful
        """

        account = self.db.query(AmazonAccount).filter(
            AmazonAccount.id == account_id
        ).first()

        if not account:
            logger.error(f"Account {account_id} not found")
            return False

        # Mark as disconnected
        account.status = "disconnected"
        self.db.commit()

        logger.info(f"Amazon account {account_id} disconnected")
        return True

    def get_accounts(self, user_id: int) -> List[AmazonAccount]:
        """
        Get all Amazon accounts for a user.

        Args:
            user_id: User ID

        Returns:
            List of AmazonAccount
        """

        return self.db.query(AmazonAccount).filter(
            AmazonAccount.user_id == user_id
        ).all()

    def get_account(self, account_id: int) -> Optional[AmazonAccount]:
        """
        Get single Amazon account.

        Args:
            account_id: Amazon account ID

        Returns:
            AmazonAccount or None
        """

        return self.db.query(AmazonAccount).filter(
            AmazonAccount.id == account_id
        ).first()

    # ========================================================================
    # PRODUCT RESEARCH
    # ========================================================================

    def research_products(
        self,
        account_id: int,
        keywords: str,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search Amazon catalog for product research.

        Args:
            account_id: Amazon account ID
            keywords: Search keywords
            max_results: Max results to return

        Returns:
            List of product research results with profitability analysis

        Example:
            results = service.research_products(
                account_id=1,
                keywords="yoga mat",
                max_results=10
            )
        """

        account = self.get_account(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")

        client = self._get_client(account)

        logger.info(f"Researching products: {keywords}")

        try:
            # Search catalog
            response = client.search_catalog(
                keywords=keywords,
                page_size=max_results,
                included_data=["summaries", "images", "salesRanks"]
            )

            products = []

            for item in response.get("items", []):
                asin = item.get("asin")

                # Get basic info
                product_info = {
                    "asin": asin,
                    "title": item.get("summaries", [{}])[0].get("itemName", ""),
                    "brand": item.get("summaries", [{}])[0].get("brand", ""),
                    "main_image": item.get("images", [{}])[0].get("images", [{}])[0].get("link", ""),
                    "sales_rank": None,
                    "category": None
                }

                # Extract sales rank
                sales_ranks = item.get("salesRanks", [])
                if sales_ranks:
                    product_info["sales_rank"] = sales_ranks[0].get("rank")
                    product_info["category"] = sales_ranks[0].get("displayGroupTitle")

                # Get competitive pricing
                try:
                    pricing = client.get_competitive_pricing(asin)
                    product_info["buy_box_price"] = pricing.get("payload", [{}])[0].get("Product", {}).get("CompetitivePricing", {}).get("CompetitivePrices", [{}])[0].get("Price", {}).get("ListingPrice", {}).get("Amount")
                except:
                    product_info["buy_box_price"] = None

                # Estimate fees (if we have price)
                if product_info["buy_box_price"]:
                    try:
                        fees_response = client.get_product_fees_estimate(
                            asin=asin,
                            price=float(product_info["buy_box_price"]),
                            is_fba=True
                        )

                        fees_estimate = fees_response.get("payload", {}).get("FeesEstimate", {})
                        total_fees = fees_estimate.get("TotalFeesEstimate", {}).get("Amount", 0)

                        product_info["estimated_fees"] = total_fees
                        product_info["estimated_profit"] = float(product_info["buy_box_price"]) - total_fees

                    except:
                        product_info["estimated_fees"] = None
                        product_info["estimated_profit"] = None

                products.append(product_info)

            logger.info(f"Found {len(products)} products")
            return products

        except Exception as e:
            logger.error(f"Product research error: {e}")
            return []

    def analyze_product_profitability(
        self,
        account_id: int,
        asin: str,
        cost: float
    ) -> Dict[str, Any]:
        """
        Analyze profitability for a specific product.

        Args:
            account_id: Amazon account ID
            asin: Product ASIN
            cost: Your cost per unit

        Returns:
            Profitability analysis

        Example:
            analysis = service.analyze_product_profitability(
                account_id=1,
                asin="B08XYZ123",
                cost=10.50
            )
        """

        account = self.get_account(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")

        client = self._get_client(account)

        logger.info(f"Analyzing profitability for ASIN {asin}")

        try:
            # Get product details
            product = client.get_catalog_item(
                asin=asin,
                included_data=["summaries", "salesRanks"]
            )

            # Get competitive pricing
            pricing = client.get_competitive_pricing(asin)
            buy_box_price = pricing.get("payload", [{}])[0].get("Product", {}).get("CompetitivePricing", {}).get("CompetitivePrices", [{}])[0].get("Price", {}).get("ListingPrice", {}).get("Amount", 0)

            # Get fee estimate
            fees_response = client.get_product_fees_estimate(
                asin=asin,
                price=float(buy_box_price),
                is_fba=True
            )

            fees_estimate = fees_response.get("payload", {}).get("FeesEstimate", {})
            fee_breakdown = {}

            for fee_detail in fees_estimate.get("FeeDetailList", []):
                fee_type = fee_detail.get("FeeType")
                fee_amount = fee_detail.get("FinalFee", {}).get("Amount", 0)
                fee_breakdown[fee_type] = fee_amount

            total_fees = fees_estimate.get("TotalFeesEstimate", {}).get("Amount", 0)

            # Calculate profitability
            revenue = float(buy_box_price)
            profit = revenue - total_fees - cost
            roi = (profit / cost * 100) if cost > 0 else 0
            margin = (profit / revenue * 100) if revenue > 0 else 0

            analysis = {
                "asin": asin,
                "title": product.get("summaries", [{}])[0].get("itemName", ""),
                "buy_box_price": revenue,
                "cost": cost,
                "fees": {
                    "total": total_fees,
                    "breakdown": fee_breakdown
                },
                "profit": profit,
                "roi_percent": roi,
                "margin_percent": margin,
                "sales_rank": product.get("salesRanks", [{}])[0].get("rank"),
                "category": product.get("salesRanks", [{}])[0].get("displayGroupTitle"),
                "recommendation": "✅ Profitable" if profit > 5 and margin > 20 else "⚠️ Low margin" if profit > 0 else "❌ Unprofitable"
            }

            logger.info(f"Analysis complete: {analysis['recommendation']}")
            return analysis

        except Exception as e:
            logger.error(f"Profitability analysis error: {e}")
            raise

    # ========================================================================
    # LISTING MANAGEMENT
    # ========================================================================

    def create_listing(
        self,
        account_id: int,
        sku: str,
        asin: Optional[str],
        title: str,
        price: float,
        cost: float,
        quantity: int,
        condition: str = "new_new",
        fulfillment_channel: str = "FBA",
        description: Optional[str] = None,
        bullet_points: Optional[List[str]] = None,
        main_image: Optional[str] = None,
        shopify_product_id: Optional[int] = None
    ) -> AmazonListing:
        """
        Create Amazon product listing.

        Args:
            account_id: Amazon account ID
            sku: Your SKU
            asin: ASIN (if matching existing product)
            title: Product title
            price: Selling price
            cost: Your cost
            quantity: Inventory quantity
            condition: Condition type
            fulfillment_channel: "FBA" or "FBM"
            description: Product description
            bullet_points: Feature bullets (up to 5)
            main_image: Main image URL
            shopify_product_id: Link to Shopify product

        Returns:
            Created AmazonListing
        """

        account = self.get_account(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")

        logger.info(f"Creating Amazon listing: {sku}")

        # Create listing in database
        listing = AmazonListing(
            user_id=account.user_id,
            account_id=account_id,
            asin=asin,
            sku=sku,
            title=title,
            price=price,
            cost=cost,
            fulfillment_channel=fulfillment_channel,
            inventory_quantity=quantity,
            description=description,
            bullet_points=bullet_points or [],
            main_image=main_image,
            shopify_product_id=shopify_product_id,
            status="draft"
        )

        self.db.add(listing)
        self.db.commit()
        self.db.refresh(listing)

        logger.info(f"Listing {sku} created (draft)")
        return listing

    def publish_listing(self, listing_id: int) -> bool:
        """
        Publish listing to Amazon.

        Args:
            listing_id: Listing ID

        Returns:
            True if successful
        """

        listing = self.db.query(AmazonListing).filter(
            AmazonListing.id == listing_id
        ).first()

        if not listing:
            logger.error(f"Listing {listing_id} not found")
            return False

        account = self.get_account(listing.account_id)
        if not account:
            logger.error(f"Account {listing.account_id} not found")
            return False

        client = self._get_client(account)

        logger.info(f"Publishing listing: {listing.sku}")

        try:
            # Build attributes for SP-API
            attributes = {
                "condition_type": [{"value": "new_new", "marketplace_id": account.marketplace_id}],
                "item_name": [{"value": listing.title, "marketplace_id": account.marketplace_id}],
                "list_price": [{"value": listing.price, "currency": "USD", "marketplace_id": account.marketplace_id}],
            }

            if listing.description:
                attributes["product_description"] = [{"value": listing.description, "marketplace_id": account.marketplace_id}]

            if listing.bullet_points:
                for i, bullet in enumerate(listing.bullet_points[:5]):
                    attributes[f"bullet_point_{i+1}"] = [{"value": bullet, "marketplace_id": account.marketplace_id}]

            # Create/update listing via SP-API
            response = client.create_or_update_listing(
                seller_sku=listing.sku,
                product_type="PRODUCT",  # Generic - should be specific to category
                requirements="LISTING",
                attributes=attributes,
                marketplace_ids=[account.marketplace_id]
            )

            # Update status
            listing.status = "active"
            self.db.commit()

            logger.info(f"✅ Listing {listing.sku} published")
            return True

        except Exception as e:
            listing.status = "error"
            self.db.commit()
            logger.error(f"❌ Failed to publish listing: {e}")
            return False

    def sync_listings(self, account_id: int) -> int:
        """
        Sync all listings from Amazon.

        Args:
            account_id: Amazon account ID

        Returns:
            Number of listings synced
        """

        account = self.get_account(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")

        client = self._get_client(account)

        logger.info(f"Syncing listings for account {account_id}")

        # For now, just update last_sync timestamp
        # Full implementation would use Reports API to get all listings

        account.last_sync_at = datetime.utcnow()
        self.db.commit()

        logger.info("Listings sync complete")
        return 0

    # ========================================================================
    # ORDER MANAGEMENT
    # ========================================================================

    def sync_orders(
        self,
        account_id: int,
        created_after: Optional[str] = None,
        days_back: int = 7
    ) -> int:
        """
        Sync orders from Amazon.

        Args:
            account_id: Amazon account ID
            created_after: ISO 8601 date to sync from (or None for days_back)
            days_back: Days to look back if created_after not provided

        Returns:
            Number of orders synced
        """

        account = self.get_account(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")

        client = self._get_client(account)

        # Default date range
        if not created_after:
            created_after = (datetime.utcnow() - timedelta(days=days_back)).isoformat() + "Z"

        logger.info(f"Syncing orders since {created_after}")

        try:
            response = client.get_orders(
                created_after=created_after,
                marketplace_ids=[account.marketplace_id],
                max_results=100
            )

            orders = response.get("payload", {}).get("Orders", [])
            synced_count = 0

            for order_data in orders:
                amazon_order_id = order_data.get("AmazonOrderId")

                # Check if order exists
                existing = self.db.query(AmazonOrder).filter(
                    AmazonOrder.amazon_order_id == amazon_order_id
                ).first()

                if existing:
                    # Update existing
                    existing.order_status = order_data.get("OrderStatus")
                    existing.order_total = float(order_data.get("OrderTotal", {}).get("Amount", 0))
                    existing.last_update_date = datetime.fromisoformat(order_data.get("LastUpdateDate", "").replace("Z", ""))
                else:
                    # Create new
                    order = AmazonOrder(
                        user_id=account.user_id,
                        account_id=account_id,
                        amazon_order_id=amazon_order_id,
                        marketplace_id=order_data.get("MarketplaceId"),
                        order_status=order_data.get("OrderStatus"),
                        fulfillment_channel=order_data.get("FulfillmentChannel"),
                        order_total=float(order_data.get("OrderTotal", {}).get("Amount", 0)),
                        currency=order_data.get("OrderTotal", {}).get("CurrencyCode", "USD"),
                        buyer_email=order_data.get("BuyerEmail"),
                        purchase_date=datetime.fromisoformat(order_data.get("PurchaseDate", "").replace("Z", "")),
                        last_update_date=datetime.fromisoformat(order_data.get("LastUpdateDate", "").replace("Z", ""))
                    )
                    self.db.add(order)

                synced_count += 1

            self.db.commit()

            account.last_sync_at = datetime.utcnow()
            self.db.commit()

            logger.info(f"✅ Synced {synced_count} orders")
            return synced_count

        except Exception as e:
            logger.error(f"❌ Order sync error: {e}")
            return 0

    # ========================================================================
    # FBA INVENTORY
    # ========================================================================

    def sync_inventory(self, account_id: int) -> int:
        """
        Sync FBA inventory from Amazon.

        Args:
            account_id: Amazon account ID

        Returns:
            Number of SKUs synced
        """

        account = self.get_account(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")

        client = self._get_client(account)

        logger.info(f"Syncing FBA inventory for account {account_id}")

        try:
            response = client.get_inventory_summaries(
                granularity_type="Marketplace",
                marketplace_ids=[account.marketplace_id],
                details=True
            )

            summaries = response.get("payload", {}).get("inventorySummaries", [])
            synced_count = 0

            for summary in summaries:
                sku = summary.get("sellerSKU")
                asin = summary.get("asin")

                # Find listing
                listing = self.db.query(AmazonListing).filter(
                    and_(
                        AmazonListing.account_id == account_id,
                        AmazonListing.sku == sku
                    )
                ).first()

                if listing:
                    # Update inventory
                    listing.inventory_quantity = summary.get("totalQuantity", 0)
                    listing.reserved_quantity = summary.get("reservedQuantity", {}).get("totalReservedQuantity", 0)
                    listing.inbound_quantity = summary.get("inboundWorkingQuantity", 0)
                    synced_count += 1

            self.db.commit()

            logger.info(f"✅ Synced inventory for {synced_count} SKUs")
            return synced_count

        except Exception as e:
            logger.error(f"❌ Inventory sync error: {e}")
            return 0

    # ========================================================================
    # STATISTICS
    # ========================================================================

    def get_account_statistics(self, account_id: int) -> Dict[str, Any]:
        """
        Get statistics for an Amazon account.

        Args:
            account_id: Amazon account ID

        Returns:
            Account statistics
        """

        account = self.get_account(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")

        # Count listings by status
        listings_count = self.db.query(AmazonListing).filter(
            AmazonListing.account_id == account_id
        ).count()

        active_listings = self.db.query(AmazonListing).filter(
            and_(
                AmazonListing.account_id == account_id,
                AmazonListing.status == "active"
            )
        ).count()

        # Count orders (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_orders = self.db.query(AmazonOrder).filter(
            and_(
                AmazonOrder.account_id == account_id,
                AmazonOrder.purchase_date >= thirty_days_ago
            )
        ).count()

        # Calculate total revenue (last 30 days)
        orders = self.db.query(AmazonOrder).filter(
            and_(
                AmazonOrder.account_id == account_id,
                AmazonOrder.purchase_date >= thirty_days_ago
            )
        ).all()

        total_revenue = sum(order.order_total for order in orders)

        # Count shipments
        shipments_count = self.db.query(FBAShipment).filter(
            FBAShipment.account_id == account_id
        ).count()

        return {
            "account_id": account_id,
            "account_name": account.account_name,
            "marketplace_id": account.marketplace_id,
            "status": account.status,
            "last_sync_at": account.last_sync_at.isoformat() if account.last_sync_at else None,
            "listings": {
                "total": listings_count,
                "active": active_listings
            },
            "orders_30d": recent_orders,
            "revenue_30d": float(total_revenue),
            "shipments": shipments_count
        }
