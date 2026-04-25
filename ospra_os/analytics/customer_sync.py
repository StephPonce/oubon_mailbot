"""
Customer Sync - Shopify Integration

Syncs customer data from Shopify and calculates analytics metrics:
- Fetches customers and orders from Shopify Admin API
- Calculates RFM scores, LTV, churn probability
- Updates customer database with latest metrics
- Handles incremental sync (only changed customers)
"""
from datetime import datetime, timedelta, date, timezone
from typing import Dict, List, Optional, Tuple
import logging
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ospra_os.models.customer import Customer, CustomerSnapshot, CustomerEvent, CustomerCohort
from ospra_os.analytics.customer_analytics import CustomerAnalytics
from ospra_os.analytics.ltv_calculator import get_ltv_calculator
from ospra_os.analytics.churn_predictor import get_churn_predictor

logger = logging.getLogger(__name__)


class CustomerSync:
    """Sync customers from Shopify and calculate analytics"""

    def __init__(
        self,
        shopify_store: str,
        shopify_api_token: str,
        db_session: AsyncSession = None
    ):
        """
        Initialize Customer Sync

        Args:
            shopify_store: Shopify store URL (e.g., 'mystore.myshopify.com')
            shopify_api_token: Shopify Admin API access token
            db_session: Database session for storing data
        """
        self.shopify_store = shopify_store
        self.shopify_api_token = shopify_api_token
        self.db = db_session
        self.analytics = CustomerAnalytics(db_session)
        self.api_version = "2025-01"  # Shopify API version
        self.base_url = f"https://{shopify_store}/admin/api/{self.api_version}"

    # ==================== Shopify API Calls ====================

    async def fetch_shopify_customers(
        self,
        limit: int = 250,
        since_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetch customers from Shopify Admin API

        Args:
            limit: Number of customers per page (max 250)
            since_id: Fetch customers after this ID (for pagination)

        Returns:
            List of customer dictionaries from Shopify
        """
        logger.info(f" Fetching customers from Shopify (limit: {limit})...")

        url = f"{self.base_url}/customers.json"
        headers = {
            "X-Shopify-Access-Token": self.shopify_api_token,
            "Content-Type": "application/json"
        }

        params = {"limit": limit}
        if since_id:
            params["since_id"] = since_id

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                customers = data.get("customers", [])

                logger.info(f"[SUCCESS] Fetched {len(customers)} customers from Shopify")
                return customers

            except httpx.HTTPError as e:
                logger.error(f"[ERROR] Error fetching Shopify customers: {e}")
                return []

    async def fetch_customer_orders(self, shopify_customer_id: str) -> List[Dict]:
        """
        Fetch all orders for a specific customer

        Args:
            shopify_customer_id: Shopify customer ID

        Returns:
            List of order dictionaries
        """
        logger.info(f"[PACKAGE] Fetching orders for customer: {shopify_customer_id}")

        url = f"{self.base_url}/customers/{shopify_customer_id}/orders.json"
        headers = {
            "X-Shopify-Access-Token": self.shopify_api_token,
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                orders = data.get("orders", [])

                logger.info(f"[SUCCESS] Fetched {len(orders)} orders")
                return orders

            except httpx.HTTPError as e:
                logger.error(f"[ERROR] Error fetching orders: {e}")
                return []

    async def fetch_all_customers(self) -> List[Dict]:
        """
        Fetch all customers from Shopify using pagination

        Returns:
            Complete list of all customers
        """
        logger.info(" Fetching ALL customers from Shopify (with pagination)...")

        all_customers = []
        since_id = None
        page = 1

        while True:
            customers = await self.fetch_shopify_customers(limit=250, since_id=since_id)

            if not customers:
                break

            all_customers.extend(customers)
            logger.info(f"   Page {page}: {len(customers)} customers (total: {len(all_customers)})")

            # Get last customer ID for next page
            since_id = customers[-1].get("id")
            page += 1

            # Safety limit to prevent infinite loops
            if page > 100:
                logger.warning("[WARNING]  Reached page limit (100), stopping pagination")
                break

        logger.info(f"[SUCCESS] Fetched total of {len(all_customers)} customers")
        return all_customers

    # ==================== Data Transformation ====================

    def transform_shopify_customer(self, shopify_customer: Dict, orders: List[Dict]) -> Dict:
        """
        Transform Shopify customer data into our analytics format

        Args:
            shopify_customer: Raw Shopify customer data
            orders: Customer's orders from Shopify

        Returns:
            Transformed customer dictionary
        """
        customer_id = f"shopify_{shopify_customer['id']}"

        # Parse acquisition date (created_at)
        created_at_str = shopify_customer.get('created_at', '')
        if created_at_str:
            acquisition_date = datetime.fromisoformat(created_at_str.replace('Z', '+00:00')).date()
        else:
            acquisition_date = date.today()

        # Transform orders
        transformed_orders = []
        total_revenue = 0.0

        for order in orders:
            order_date = order.get('created_at', '')
            order_total = float(order.get('total_price', 0))
            discount_amount = sum(
                float(disc.get('amount', 0))
                for disc in order.get('discount_applications', [])
            )

            # Transform line items
            items = []
            for item in order.get('line_items', []):
                items.append({
                    "product_name": item.get('title', ''),
                    "product_id": str(item.get('product_id', '')),
                    "category": item.get('product_type', 'Uncategorized'),
                    "brand": item.get('vendor', 'Unknown'),
                    "price": float(item.get('price', 0)),
                    "quantity": item.get('quantity', 1)
                })

            transformed_orders.append({
                "order_id": str(order.get('id', '')),
                "date": order_date,
                "total": order_total,
                "discount_amount": discount_amount,
                "items": items
            })

            total_revenue += order_total

        # Determine acquisition source
        # TODO: Enhance with UTM tracking from Shopify customer tags/notes
        acquisition_source = "organic"  # Default
        tags = shopify_customer.get('tags', '').lower()
        if 'facebook' in tags or 'fb' in tags:
            acquisition_source = "facebook_ads"
        elif 'google' in tags:
            acquisition_source = "google_ads"
        elif 'instagram' in tags or 'ig' in tags:
            acquisition_source = "instagram"

        # Build customer data
        customer_data = {
            "customer_id": customer_id,
            "shopify_customer_id": str(shopify_customer['id']),
            "email": shopify_customer.get('email', ''),
            "first_name": shopify_customer.get('first_name', ''),
            "last_name": shopify_customer.get('last_name', ''),
            "phone": shopify_customer.get('phone', ''),
            "acquisition_date": acquisition_date.isoformat(),
            "acquisition_source": acquisition_source,
            "total_orders": len(orders),
            "orders": transformed_orders
        }

        return customer_data

    # ==================== Metrics Calculation ====================

    async def calculate_customer_metrics(self, customer_data: Dict) -> Dict:
        """
        Calculate all analytics metrics for a customer

        Args:
            customer_data: Transformed customer data

        Returns:
            Customer data with calculated metrics
        """
        customer_id = customer_data['customer_id']
        logger.info(f" Calculating metrics for: {customer_id}")

        # Get complete profile (includes RFM, segment)
        profile = await self.analytics.get_customer_profile(customer_id, customer_data)

        # Calculate LTV
        ltv_calculator = get_ltv_calculator(self.db)
        historical_ltv = ltv_calculator.calculate_historical_ltv(
            customer_id,
            customer_data.get('orders', [])
        )

        predictive_ltv = await ltv_calculator.calculate_predictive_ltv(
            customer_id,
            profile
        )

        # Calculate churn probability
        churn_predictor = get_churn_predictor(self.db)
        churn_prob = await churn_predictor.calculate_churn_probability(
            customer_id,
            profile
        )

        # Determine risk level
        if churn_prob < 0.3:
            risk_level = "LOW"
        elif churn_prob < 0.6:
            risk_level = "MEDIUM"
        else:
            risk_level = "HIGH"

        # Update profile with calculated metrics
        profile.update({
            "ltv": historical_ltv,
            "predicted_ltv": predictive_ltv.get('predicted_total_ltv'),
            "churn_probability": churn_prob,
            "risk_level": risk_level
        })

        logger.info(f"[SUCCESS] Metrics calculated - LTV: ${historical_ltv:.2f}, Segment: {profile['segment']}, Risk: {risk_level}")

        return profile

    # ==================== Database Operations ====================

    async def save_customer_to_db(self, customer_profile: Dict) -> Customer:
        """
        Save or update customer in database

        Args:
            customer_profile: Complete customer profile with metrics

        Returns:
            Customer database record
        """
        if not self.db:
            logger.warning("[WARNING]  No database session, skipping save")
            return None

        customer_id = customer_profile['customer_id']
        logger.info(f" Saving customer to database: {customer_id}")

        # Check if customer exists
        stmt = select(Customer).where(Customer.customer_id == customer_id)
        result = await self.db.execute(stmt)
        existing_customer = result.scalar_one_or_none()

        # Prepare customer data
        customer_dict = {
            "customer_id": customer_id,
            "shopify_customer_id": customer_profile.get('shopify_customer_id'),
            "store_id": self.shopify_store,
            "email": customer_profile.get('email'),
            "first_name": customer_profile.get('first_name'),
            "last_name": customer_profile.get('last_name'),
            "phone": customer_profile.get('phone'),
            "acquisition_source": customer_profile.get('acquisition_source'),
            "acquisition_date": datetime.fromisoformat(customer_profile['acquisition_date']).date() if customer_profile.get('acquisition_date') else None,
            "total_orders": customer_profile.get('total_orders', 0),
            "total_revenue": customer_profile.get('ltv', 0),
            "average_order_value": customer_profile.get('average_order_value', 0),
            "ltv": customer_profile.get('ltv', 0),
            "predicted_ltv": customer_profile.get('predicted_ltv'),
            "rfm_recency": customer_profile.get('rfm_recency'),
            "rfm_frequency": customer_profile.get('rfm_frequency'),
            "rfm_monetary": customer_profile.get('rfm_monetary'),
            "rfm_score": customer_profile.get('rfm_score'),
            "segment": customer_profile.get('segment'),
            "previous_segment": existing_customer.segment if existing_customer else None,
            "last_order_date": datetime.fromisoformat(customer_profile['last_order_date']).date() if customer_profile.get('last_order_date') else None,
            "days_since_last_order": customer_profile.get('days_since_last_order'),
            "purchase_frequency_days": customer_profile.get('purchase_frequency_days'),
            "churn_probability": customer_profile.get('churn_probability'),
            "risk_level": customer_profile.get('risk_level'),
            "metrics_updated_at": datetime.now(timezone.utc)
        }

        if existing_customer:
            # Update existing customer
            for key, value in customer_dict.items():
                if key != 'customer_id':  # Don't update primary key
                    setattr(existing_customer, key, value)

            existing_customer.updated_at = datetime.now(timezone.utc)
            logger.info(f"[SUCCESS] Updated existing customer: {customer_id}")
            return existing_customer

        else:
            # Create new customer
            new_customer = Customer(**customer_dict)
            self.db.add(new_customer)
            logger.info(f"[SUCCESS] Created new customer: {customer_id}")
            return new_customer

    async def create_customer_snapshot(self, customer_profile: Dict):
        """
        Create daily snapshot for trending analysis

        Args:
            customer_profile: Customer profile with metrics
        """
        if not self.db:
            return

        snapshot = CustomerSnapshot(
            customer_id=customer_profile['customer_id'],
            snapshot_date=date.today(),
            total_orders=customer_profile.get('total_orders', 0),
            total_revenue=customer_profile.get('ltv', 0),
            ltv=customer_profile.get('ltv', 0),
            rfm_score=customer_profile.get('rfm_score'),
            segment=customer_profile.get('segment'),
            churn_probability=customer_profile.get('churn_probability')
        )

        self.db.add(snapshot)
        logger.info(f" Created snapshot for: {customer_profile['customer_id']}")

    # ==================== Full Sync ====================

    async def sync_all_customers(
        self,
        include_orders: bool = True,
        calculate_metrics: bool = True,
        save_to_db: bool = True
    ) -> List[Dict]:
        """
        Full sync of all customers from Shopify

        Args:
            include_orders: Fetch orders for each customer
            calculate_metrics: Calculate analytics metrics
            save_to_db: Save to database

        Returns:
            List of customer profiles
        """
        logger.info("[REFRESH] Starting full customer sync from Shopify...")

        # Fetch all customers
        shopify_customers = await self.fetch_all_customers()

        if not shopify_customers:
            logger.warning("[WARNING]  No customers found in Shopify")
            return []

        customer_profiles = []

        for idx, shopify_customer in enumerate(shopify_customers):
            try:
                logger.info(f"   Processing {idx + 1}/{len(shopify_customers)}: {shopify_customer.get('email', 'unknown')}")

                # Fetch orders if requested
                orders = []
                if include_orders:
                    orders = await self.fetch_customer_orders(shopify_customer['id'])

                # Transform data
                customer_data = self.transform_shopify_customer(shopify_customer, orders)

                # Calculate metrics if requested
                if calculate_metrics:
                    customer_profile = await self.calculate_customer_metrics(customer_data)
                else:
                    customer_profile = customer_data

                # Save to database if requested
                if save_to_db and self.db:
                    await self.save_customer_to_db(customer_profile)
                    await self.create_customer_snapshot(customer_profile)

                customer_profiles.append(customer_profile)

            except Exception as e:
                logger.error(f"[ERROR] Error processing customer {shopify_customer.get('id')}: {e}")
                continue

        # Commit database changes
        if save_to_db and self.db:
            await self.db.commit()
            logger.info("[SUCCESS] Database changes committed")

        logger.info(f"[SUCCESS] Full sync complete: {len(customer_profiles)} customers processed")

        return customer_profiles

    async def sync_single_customer(
        self,
        shopify_customer_id: str,
        save_to_db: bool = True
    ) -> Optional[Dict]:
        """
        Sync a single customer by Shopify ID

        Args:
            shopify_customer_id: Shopify customer ID
            save_to_db: Save to database

        Returns:
            Customer profile or None
        """
        logger.info(f"[REFRESH] Syncing single customer: {shopify_customer_id}")

        # Fetch customer
        url = f"{self.base_url}/customers/{shopify_customer_id}.json"
        headers = {
            "X-Shopify-Access-Token": self.shopify_api_token,
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                shopify_customer = data.get("customer")

                if not shopify_customer:
                    logger.error(f"[ERROR] Customer not found: {shopify_customer_id}")
                    return None

                # Fetch orders
                orders = await self.fetch_customer_orders(shopify_customer_id)

                # Transform and calculate
                customer_data = self.transform_shopify_customer(shopify_customer, orders)
                customer_profile = await self.calculate_customer_metrics(customer_data)

                # Save to database
                if save_to_db and self.db:
                    await self.save_customer_to_db(customer_profile)
                    await self.create_customer_snapshot(customer_profile)
                    await self.db.commit()

                logger.info(f"[SUCCESS] Customer synced: {customer_profile['customer_id']}")

                return customer_profile

            except httpx.HTTPError as e:
                logger.error(f"[ERROR] Error syncing customer: {e}")
                return None

    # ==================== Incremental Sync ====================

    async def sync_updated_customers(
        self,
        since_datetime: datetime,
        save_to_db: bool = True
    ) -> List[Dict]:
        """
        Sync only customers updated since a specific datetime

        Args:
            since_datetime: Only sync customers updated after this time
            save_to_db: Save to database

        Returns:
            List of updated customer profiles
        """
        logger.info(f"[REFRESH] Syncing customers updated since: {since_datetime.isoformat()}")

        # Shopify API uses 'updated_at_min' parameter
        url = f"{self.base_url}/customers.json"
        headers = {
            "X-Shopify-Access-Token": self.shopify_api_token,
            "Content-Type": "application/json"
        }

        params = {
            "updated_at_min": since_datetime.isoformat(),
            "limit": 250
        }

        customer_profiles = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                shopify_customers = data.get("customers", [])

                logger.info(f" Found {len(shopify_customers)} updated customers")

                for shopify_customer in shopify_customers:
                    # Fetch orders
                    orders = await self.fetch_customer_orders(shopify_customer['id'])

                    # Transform and calculate
                    customer_data = self.transform_shopify_customer(shopify_customer, orders)
                    customer_profile = await self.calculate_customer_metrics(customer_data)

                    # Save to database
                    if save_to_db and self.db:
                        await self.save_customer_to_db(customer_profile)
                        await self.create_customer_snapshot(customer_profile)

                    customer_profiles.append(customer_profile)

                # Commit changes
                if save_to_db and self.db:
                    await self.db.commit()

                logger.info(f"[SUCCESS] Incremental sync complete: {len(customer_profiles)} customers")

                return customer_profiles

            except httpx.HTTPError as e:
                logger.error(f"[ERROR] Error syncing updated customers: {e}")
                return []


# Factory function
def create_customer_sync(
    shopify_store: str,
    shopify_api_token: str,
    db_session: AsyncSession = None
) -> CustomerSync:
    """Create CustomerSync instance"""
    return CustomerSync(shopify_store, shopify_api_token, db_session)


logger.info("[SUCCESS] Customer Sync module loaded")
