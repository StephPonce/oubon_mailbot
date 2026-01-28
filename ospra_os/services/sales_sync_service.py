"""
Sales Sync Service - G4: Complete Feedback Loop Phase 2
======================================================

Syncs sales data from e-commerce platforms (Shopify, Amazon) to track
real-world product performance. This is the CRITICAL first step that
enables the entire feedback loop system.

Without real sales data, the AI cannot learn what actually works.
"""

import httpx
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from ospra_os.database import (
    Store, Product, ProductPerformance,
    Platform, get_session
)


class SalesSyncService:
    """
    Syncs sales data from e-commerce platforms to ProductPerformance table.

    This service:
    1. Fetches orders from Shopify/Amazon API
    2. Aggregates sales by product + date
    3. Calculates metrics (revenue, profit, conversion, ROAS)
    4. Saves daily snapshots to ProductPerformance table

    Usage:
        service = SalesSyncService(db)
        result = await service.sync_store(store, days_back=7)
    """

    def __init__(self, db: Session):
        self.db = db

    async def sync_store(
        self,
        store: Store,
        days_back: int = 7
    ) -> Dict:
        """
        Sync orders from a single store.

        Args:
            store: Store model instance
            days_back: Number of days to sync (default 7)

        Returns:
            {
                "success": True,
                "store_id": 1,
                "platform": "shopify",
                "days_synced": 7,
                "products_updated": 15,
                "total_revenue": 5432.10,
                "total_orders": 45,
                "errors": []
            }
        """
        print(f"[STATS] Syncing sales for store: {store.store_name} ({store.platform.value})")

        if store.platform == Platform.SHOPIFY:
            return await self._sync_shopify_store(store, days_back)
        elif store.platform == Platform.AMAZON:
            return await self._sync_amazon_store(store, days_back)
        else:
            return {
                "success": False,
                "error": f"Platform {store.platform} not yet supported"
            }

    async def sync_all_stores(
        self,
        user_id: Optional[int] = None,
        days_back: int = 1
    ) -> List[Dict]:
        """
        Sync all active stores (optionally for specific user).

        Args:
            user_id: If provided, only sync stores for this user
            days_back: Number of days to sync

        Returns:
            List of sync results for each store
        """
        query = self.db.query(Store).filter(Store.is_active == True)

        if user_id:
            query = query.filter(Store.user_id == user_id)

        stores = query.all()

        # PERFORMANCE FIX: Use asyncio.gather for concurrent store syncs
        # This reduces sync time from O(n * store_sync_time) to O(store_sync_time)
        # With 50 stores, this means ~5 seconds instead of ~250 seconds

        async def sync_store_safe(store):
            """Wrapper to catch exceptions without failing the entire batch."""
            try:
                return await self.sync_store(store, days_back)
            except Exception as e:
                logger.error(f"Error syncing store {store.id}: {e}")
                return {
                    "success": False,
                    "store_id": store.id,
                    "error": str(e)
                }

        # Run all store syncs concurrently (with reasonable concurrency limit)
        import asyncio
        semaphore = asyncio.Semaphore(10)  # Limit to 10 concurrent syncs

        async def sync_with_semaphore(store):
            async with semaphore:
                return await sync_store_safe(store)

        results = await asyncio.gather(
            *[sync_with_semaphore(store) for store in stores]
        )

        return list(results)

    async def _sync_shopify_store(
        self,
        store: Store,
        days_back: int
    ) -> Dict:
        """
        Sync orders from Shopify store.

        Shopify Orders API:
        GET /admin/api/2024-10/orders.json
        Parameters:
        - created_at_min: ISO timestamp
        - status: any (to include all orders)
        - limit: 250 (max per request)
        - fields: id,line_items,created_at,financial_status,total_price
        """
        try:
            credentials = store.get_credentials()
            shop_url = credentials.get("shop_url")
            access_token = credentials.get("access_token")
            api_version = credentials.get("api_version", "2024-10")

            if not shop_url or not access_token:
                return {
                    "success": False,
                    "error": "Missing Shopify credentials"
                }

            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            # Fetch orders from Shopify
            base_url = f"https://{shop_url}/admin/api/{api_version}"
            headers = {
                'X-Shopify-Access-Token': access_token,
                'Content-Type': 'application/json'
            }

            all_orders = []
            page_info = None

            async with httpx.AsyncClient(timeout=30.0) as client:
                while True:
                    # Build URL with pagination
                    if page_info:
                        url = f"{base_url}/orders.json?page_info={page_info}&limit=250"
                    else:
                        url = f"{base_url}/orders.json"
                        params = {
                            "created_at_min": start_date.isoformat(),
                            "status": "any",
                            "limit": 250
                        }
                        response = await client.get(url, headers=headers, params=params)

                    if not page_info:
                        response = await client.get(url, headers=headers, params=params)
                    else:
                        response = await client.get(url, headers=headers)

                    if response.status_code != 200:
                        print(f"[ERROR] Shopify API error: {response.status_code}")
                        print(response.text)
                        break

                    data = response.json()
                    orders = data.get("orders", [])
                    all_orders.extend(orders)

                    # Check for pagination
                    link_header = response.headers.get("Link", "")
                    if "rel=\"next\"" in link_header:
                        # Extract page_info from Link header
                        # Format: <url?page_info=xxx>; rel="next"
                        for part in link_header.split(","):
                            if "rel=\"next\"" in part:
                                page_info = part.split("page_info=")[1].split(">")[0]
                                break
                    else:
                        break

            print(f"[SUCCESS] Fetched {len(all_orders)} orders from Shopify")

            # Process orders into daily performance snapshots
            products_updated = await self._process_shopify_orders(
                store,
                all_orders,
                start_date.date(),
                end_date.date()
            )

            # Update store last_sync
            store.last_sync = datetime.now()
            store.sync_error = None
            self.db.commit()

            return {
                "success": True,
                "store_id": store.id,
                "platform": "shopify",
                "days_synced": days_back,
                "orders_fetched": len(all_orders),
                "products_updated": products_updated,
                "errors": []
            }

        except Exception as e:
            print(f"[ERROR] Shopify sync error: {e}")
            store.sync_error = str(e)
            self.db.commit()
            return {
                "success": False,
                "store_id": store.id,
                "error": str(e)
            }

    async def _process_shopify_orders(
        self,
        store: Store,
        orders: List[Dict],
        start_date: date,
        end_date: date
    ) -> int:
        """
        Process Shopify orders into ProductPerformance records.

        Groups orders by product + date and calculates metrics.

        Returns:
            Number of products updated
        """
        # PERFORMANCE FIX: Pre-load all products for this store to avoid N+1 queries
        # This reduces 300+ queries to 1 query for typical order batches
        store_products = self.db.query(Product).filter(
            Product.store_id == store.id
        ).all()

        # Create lookup dict by platform_product_id for O(1) access
        product_lookup = {
            prod.platform_product_id: prod
            for prod in store_products
            if prod.platform_product_id
        }

        # Group orders by product + date
        performance_data = {}  # {(product_id, date): metrics}

        for order in orders:
            order_date = datetime.fromisoformat(
                order["created_at"].replace("Z", "+00:00")
            ).date()

            for item in order.get("line_items", []):
                # Match product by platform_product_id
                shopify_product_id = str(item["product_id"])
                shopify_variant_id = str(item["variant_id"])

                # PERFORMANCE: Use pre-loaded lookup instead of N+1 query
                product = product_lookup.get(shopify_product_id)

                if not product:
                    # Product not tracked, skip
                    continue

                key = (product.id, order_date)

                if key not in performance_data:
                    performance_data[key] = {
                        "product_id": product.id,
                        "store_id": store.id,
                        "user_id": store.user_id,
                        "date": order_date,
                        "orders": 0,
                        "units_sold": 0,
                        "gross_revenue": 0.0,
                        "refunds": 0.0,
                        "net_revenue": 0.0,
                        "product_cost": 0.0,
                        "shipping_cost": 0.0,
                        "platform_fees": 0.0,
                        "ad_spend": 0.0,
                        "total_cost": 0.0,
                        "gross_profit": 0.0,
                        "net_profit": 0.0,
                        "profit_margin": 0.0,
                        "views": 0,
                        "add_to_carts": 0,
                        "checkout_initiated": 0,
                        "conversion_rate": 0.0,
                    }

                # Aggregate metrics
                data = performance_data[key]
                data["orders"] += 1
                data["units_sold"] += item["quantity"]

                item_price = float(item["price"])
                item_quantity = item["quantity"]
                item_total = item_price * item_quantity

                data["gross_revenue"] += item_total
                data["net_revenue"] += item_total  # TODO: Subtract refunds

                # Estimate costs (can be improved with actual cost data)
                if product.cost:
                    data["product_cost"] += float(product.cost) * item_quantity

                # Shopify fees (approx 2.9% + $0.30 per transaction)
                transaction_fee = item_total * 0.029 + 0.30
                data["platform_fees"] += transaction_fee

        # Save performance snapshots to database
        products_updated = 0

        for (product_id, perf_date), metrics in performance_data.items():
            # Calculate derived metrics
            metrics["total_cost"] = (
                metrics["product_cost"] +
                metrics["shipping_cost"] +
                metrics["platform_fees"] +
                metrics["ad_spend"]
            )

            metrics["gross_profit"] = metrics["gross_revenue"] - metrics["product_cost"]
            metrics["net_profit"] = metrics["net_revenue"] - metrics["total_cost"]

            if metrics["net_revenue"] > 0:
                metrics["profit_margin"] = (
                    (metrics["net_profit"] / metrics["net_revenue"]) * 100
                )

            # Save or update ProductPerformance
            existing = self.db.query(ProductPerformance).filter(
                and_(
                    ProductPerformance.product_id == product_id,
                    ProductPerformance.date == perf_date
                )
            ).first()

            if existing:
                # Update existing record
                for key, value in metrics.items():
                    setattr(existing, key, value)
                existing.synced_at = datetime.now()
                existing.sync_source = "shopify"
            else:
                # Create new record
                perf = ProductPerformance(
                    **metrics,
                    synced_at=datetime.now(),
                    sync_source="shopify"
                )
                self.db.add(perf)

            products_updated += 1

        self.db.commit()
        print(f"[SUCCESS] Updated {products_updated} product performance records")

        return products_updated

    async def _sync_amazon_store(
        self,
        store: Store,
        days_back: int
    ) -> Dict:
        """
        Sync orders from Amazon store.

        TODO: Implement Amazon SP-API integration
        """
        return {
            "success": False,
            "error": "Amazon sync not yet implemented"
        }

    def get_product_performance_summary(
        self,
        product_id: int,
        days: int = 30
    ) -> Dict:
        """
        Get aggregated performance summary for a product.

        Args:
            product_id: Product ID
            days: Number of days to aggregate (default 30)

        Returns:
            {
                "product_id": 123,
                "days": 30,
                "total_orders": 45,
                "total_units_sold": 67,
                "total_revenue": 3450.25,
                "total_profit": 1890.50,
                "avg_daily_orders": 1.5,
                "avg_daily_revenue": 115.01,
                "avg_margin": 54.8,
                "conversion_rate": 3.2,
                "daily_snapshots": 23  # Days with data
            }
        """
        cutoff_date = datetime.now().date() - timedelta(days=days)

        # Query performance records
        records = self.db.query(ProductPerformance).filter(
            and_(
                ProductPerformance.product_id == product_id,
                ProductPerformance.date >= cutoff_date
            )
        ).all()

        if not records:
            return {
                "product_id": product_id,
                "days": days,
                "error": "No performance data found"
            }

        # Aggregate metrics
        total_orders = sum(r.orders for r in records)
        total_units = sum(r.units_sold for r in records)
        total_revenue = sum(r.net_revenue for r in records)
        total_profit = sum(r.net_profit for r in records)

        days_with_data = len(records)

        avg_margin = (
            sum(r.profit_margin for r in records if r.profit_margin) / days_with_data
            if days_with_data > 0 else 0
        )

        return {
            "product_id": product_id,
            "days": days,
            "total_orders": total_orders,
            "total_units_sold": total_units,
            "total_revenue": round(total_revenue, 2),
            "total_profit": round(total_profit, 2),
            "avg_daily_orders": round(total_orders / days, 2),
            "avg_daily_revenue": round(total_revenue / days, 2),
            "avg_margin": round(avg_margin, 2),
            "daily_snapshots": days_with_data
        }

    def get_store_performance_summary(
        self,
        store_id: int,
        days: int = 30
    ) -> Dict:
        """
        Get aggregated performance summary for entire store.

        Returns summary across all products in the store.
        """
        cutoff_date = datetime.now().date() - timedelta(days=days)

        records = self.db.query(ProductPerformance).filter(
            and_(
                ProductPerformance.store_id == store_id,
                ProductPerformance.date >= cutoff_date
            )
        ).all()

        if not records:
            return {
                "store_id": store_id,
                "days": days,
                "error": "No performance data found"
            }

        # Count unique products
        product_ids = set(r.product_id for r in records)

        total_orders = sum(r.orders for r in records)
        total_revenue = sum(r.net_revenue for r in records)
        total_profit = sum(r.net_profit for r in records)

        return {
            "store_id": store_id,
            "days": days,
            "products_tracked": len(product_ids),
            "total_orders": total_orders,
            "total_revenue": round(total_revenue, 2),
            "total_profit": round(total_profit, 2),
            "avg_daily_revenue": round(total_revenue / days, 2),
            "overall_margin": round((total_profit / total_revenue * 100) if total_revenue > 0 else 0, 2)
        }
