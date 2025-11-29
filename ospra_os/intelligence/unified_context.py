"""
UNIFIED CONTEXT - THE BRAIN'S EYES

This is the CRITICAL component. Single source of truth that aggregates ALL data
so the AI sees EVERYTHING at once.

The AI needs to see:
- Product performance across ALL stores
- Meta/TikTok ad performance
- Email customer signals
- Social media trends
- Competitor movements
- Self-learning insights

All in one unified context.
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from ospra_os.database.multi_store_models import (
    Product, Store, AdCampaign, Platform, ProductStatus
)

logger = logging.getLogger(__name__)


class UnifiedContextBuilder:
    """
    Aggregates ALL data from ALL systems into a single unified context.
    This allows the AI to see the entire business at once and detect patterns.
    """

    def __init__(self, db: Session):
        self.db = db
        self._cache = {}
        self._cache_timestamp = {}
        self._cache_duration = 300  # 5 minutes

    async def build_full_context(
        self,
        user_id: Optional[int] = None,
        store_id: Optional[int] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Build complete unified context by aggregating ALL data sources.

        This runs all queries IN PARALLEL for speed, then correlates the data.

        Args:
            user_id: Optional user filter
            store_id: Optional store filter
            force_refresh: Skip cache and rebuild

        Returns:
            Unified context dictionary with all aggregated data
        """
        cache_key = f"context_{user_id}_{store_id}"

        # Check cache
        if not force_refresh and cache_key in self._cache:
            age = datetime.utcnow() - self._cache_timestamp.get(cache_key, datetime.min)
            if age.total_seconds() < self._cache_duration:
                logger.info(f"Using cached context (age: {age.total_seconds():.1f}s)")
                return self._cache[cache_key]

        logger.info("Building unified context from ALL data sources...")

        # Gather ALL data in parallel (FAST)
        tasks = [
            self._get_product_data(user_id, store_id),
            self._get_ad_data(user_id, store_id),
            self._get_email_signals(user_id),
            self._get_social_data(),
            self._get_competitor_data(store_id),
            self._get_self_learning_data(user_id)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Unpack results
        product_data = results[0] if not isinstance(results[0], Exception) else {}
        ad_data = results[1] if not isinstance(results[1], Exception) else {}
        email_signals = results[2] if not isinstance(results[2], Exception) else {}
        social_data = results[3] if not isinstance(results[3], Exception) else {}
        competitor_data = results[4] if not isinstance(results[4], Exception) else {}
        learning_data = results[5] if not isinstance(results[5], Exception) else {}

        # Detect correlations (the KEY intelligence function)
        correlations = self._detect_correlations(
            product_data, ad_data, email_signals, social_data, competitor_data
        )

        # Build unified context
        context = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "store_id": store_id,
            "products": product_data,
            "ads": ad_data,
            "emails": email_signals,
            "social": social_data,
            "competitors": competitor_data,
            "learning": learning_data,
            "correlations": correlations,
            "summary": self._generate_summary(
                product_data, ad_data, email_signals, social_data,
                competitor_data, learning_data, correlations
            )
        }

        # Cache it
        self._cache[cache_key] = context
        self._cache_timestamp[cache_key] = datetime.utcnow()

        logger.info(f"Unified context built: {len(correlations)} correlations detected")

        return context

    async def _get_product_data(
        self,
        user_id: Optional[int] = None,
        store_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get product performance data across all stores"""
        try:
            query = self.db.query(Product)

            if user_id:
                query = query.join(Store).filter(Store.user_id == user_id)
            if store_id:
                query = query.filter(Product.store_id == store_id)

            products = query.all()

            # Aggregate metrics
            total_products = len(products)
            active_products = len([p for p in products if p.status == ProductStatus.ACTIVE])
            total_revenue = sum(p.total_sales or 0 for p in products)
            avg_profit_margin = sum(p.profit_margin or 0 for p in products) / max(total_products, 1)

            # Best performers (by revenue)
            top_products = sorted(
                products,
                key=lambda p: p.total_sales or 0,
                reverse=True
            )[:10]

            # Worst performers
            worst_products = [
                p for p in products
                if p.status == ProductStatus.ACTIVE and (p.total_sales or 0) < 100
            ]

            return {
                "total_products": total_products,
                "active_products": active_products,
                "total_revenue": total_revenue,
                "avg_profit_margin": avg_profit_margin,
                "top_performers": [
                    {
                        "id": p.id,
                        "title": p.title,
                        "sales": p.total_sales,
                        "revenue": p.total_sales * (p.price or 0),
                        "profit_margin": p.profit_margin
                    }
                    for p in top_products
                ],
                "underperformers": [
                    {
                        "id": p.id,
                        "title": p.title,
                        "sales": p.total_sales,
                        "days_active": (datetime.utcnow() - p.deployed_at).days if p.deployed_at else 0
                    }
                    for p in worst_products[:10]
                ]
            }
        except Exception as e:
            logger.error(f"Error getting product data: {e}")
            return {}

    async def _get_ad_data(
        self,
        user_id: Optional[int] = None,
        store_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get Meta/TikTok ad performance data"""
        try:
            query = self.db.query(AdCampaign)

            if user_id:
                query = query.join(Store).filter(Store.user_id == user_id)
            if store_id:
                query = query.filter(AdCampaign.store_id == store_id)

            campaigns = query.filter(AdCampaign.status == "ACTIVE").all()

            total_spend = sum(c.budget_spent or 0 for c in campaigns)
            total_impressions = sum(c.impressions or 0 for c in campaigns)
            total_clicks = sum(c.clicks or 0 for c in campaigns)
            total_conversions = sum(c.conversions or 0 for c in campaigns)

            avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
            avg_cpc = (total_spend / total_clicks) if total_clicks > 0 else 0
            avg_roas = sum(c.roas or 0 for c in campaigns) / max(len(campaigns), 1)

            return {
                "active_campaigns": len(campaigns),
                "total_spend": total_spend,
                "total_impressions": total_impressions,
                "total_clicks": total_clicks,
                "total_conversions": total_conversions,
                "avg_ctr": avg_ctr,
                "avg_cpc": avg_cpc,
                "avg_roas": avg_roas,
                "best_campaigns": [
                    {
                        "id": c.id,
                        "name": c.campaign_name,
                        "roas": c.roas,
                        "spend": c.budget_spent,
                        "conversions": c.conversions
                    }
                    for c in sorted(campaigns, key=lambda x: x.roas or 0, reverse=True)[:5]
                ],
                "worst_campaigns": [
                    {
                        "id": c.id,
                        "name": c.campaign_name,
                        "roas": c.roas,
                        "spend": c.budget_spent,
                        "conversions": c.conversions
                    }
                    for c in sorted(campaigns, key=lambda x: x.roas or 0)[:5]
                ]
            }
        except Exception as e:
            logger.error(f"Error getting ad data: {e}")
            return {}

    async def _get_email_signals(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get customer signals from emails"""
        try:
            # This would query email database for:
            # - Customer complaints about specific products
            # - Feature requests
            # - Shipping issues
            # - Refund patterns

            # For now, return mock structure (implement when email DB is ready)
            return {
                "total_emails": 0,
                "complaints": [],
                "feature_requests": [],
                "refund_requests": [],
                "shipping_issues": []
            }
        except Exception as e:
            logger.error(f"Error getting email signals: {e}")
            return {}

    async def _get_social_data(self) -> Dict[str, Any]:
        """Get social media trend data"""
        try:
            # This would query social scrapers for:
            # - TikTok trending products
            # - Instagram trends
            # - Twitter/X trends

            # For now, return mock structure (implement when social connectors ready)
            return {
                "trending_products": [],
                "trending_niches": [],
                "viral_content": []
            }
        except Exception as e:
            logger.error(f"Error getting social data: {e}")
            return {}

    async def _get_competitor_data(self, store_id: Optional[int] = None) -> Dict[str, Any]:
        """Get competitor intelligence data"""
        try:
            # This would query competitor tracking for:
            # - New products competitors launched
            # - Price changes
            # - Stock changes
            # - New stores in niche

            # For now, return mock structure (implement when competitor engine ready)
            return {
                "tracked_competitors": 0,
                "new_products": [],
                "price_changes": [],
                "stock_changes": []
            }
        except Exception as e:
            logger.error(f"Error getting competitor data: {e}")
            return {}

    async def _get_self_learning_data(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get self-learning insights"""
        try:
            # This would query self-learning engine for:
            # - Product success patterns
            # - Failure patterns
            # - Recommendations
            # - Predictions

            from ospra_os.intelligence.self_learning import SelfLearningEngine

            learning_engine = SelfLearningEngine(self.db)
            patterns = learning_engine.analyze_product_patterns(days=30)

            return {
                "patterns": patterns,
                "recommendations": [],
                "predictions": []
            }
        except Exception as e:
            logger.error(f"Error getting self-learning data: {e}")
            return {}

    def _detect_correlations(
        self,
        product_data: Dict,
        ad_data: Dict,
        email_signals: Dict,
        social_data: Dict,
        competitor_data: Dict
    ) -> List[Dict[str, Any]]:
        """
        Detect correlations across different data sources.

        This is the KEY intelligence function - finding patterns that humans miss.

        Examples:
        - Product sales spike + email complaints = quality issue
        - Low ad ROAS + high product sales = good organic product
        - Competitor price drop + our sales drop = price war
        - Social trend + low stock = opportunity
        """
        correlations = []

        # Correlation 1: High sales + complaints = quality issue
        top_products = product_data.get("top_performers", [])
        complaints = email_signals.get("complaints", [])

        for product in top_products:
            product_complaints = [
                c for c in complaints
                if c.get("product_id") == product["id"]
            ]
            if len(product_complaints) > 5:
                correlations.append({
                    "type": "quality_issue",
                    "severity": "high",
                    "signal": f"Product '{product['title']}' has high sales but {len(product_complaints)} complaints",
                    "action": "Review product quality and supplier"
                })

        # Correlation 2: Low ROAS campaigns
        worst_campaigns = ad_data.get("worst_campaigns", [])
        for campaign in worst_campaigns:
            if campaign.get("roas", 0) < 1.0 and campaign.get("spend", 0) > 100:
                correlations.append({
                    "type": "inefficient_ad_spend",
                    "severity": "medium",
                    "signal": f"Campaign '{campaign['name']}' has ROAS {campaign.get('roas', 0):.2f} with ${campaign.get('spend', 0)} spend",
                    "action": "Pause or optimize campaign targeting"
                })

        # Correlation 3: Underperforming products
        underperformers = product_data.get("underperformers", [])
        for product in underperformers:
            if product.get("days_active", 0) > 30:
                correlations.append({
                    "type": "product_underperforming",
                    "severity": "low",
                    "signal": f"Product '{product['title']}' active for {product['days_active']} days with only {product.get('sales', 0)} sales",
                    "action": "Consider discontinuing or running ads"
                })

        return correlations

    def _generate_summary(
        self,
        product_data: Dict,
        ad_data: Dict,
        email_signals: Dict,
        social_data: Dict,
        competitor_data: Dict,
        learning_data: Dict,
        correlations: List[Dict]
    ) -> Dict[str, Any]:
        """Generate executive summary from all aggregated data"""

        # Count high-priority items
        critical_correlations = [c for c in correlations if c.get("severity") == "high"]
        medium_correlations = [c for c in correlations if c.get("severity") == "medium"]

        return {
            "total_revenue": product_data.get("total_revenue", 0),
            "active_products": product_data.get("active_products", 0),
            "ad_spend": ad_data.get("total_spend", 0),
            "avg_roas": ad_data.get("avg_roas", 0),
            "critical_issues": len(critical_correlations),
            "medium_issues": len(medium_correlations),
            "health_score": self._calculate_health_score(
                product_data, ad_data, correlations
            ),
            "top_action": critical_correlations[0] if critical_correlations else None
        }

    def _calculate_health_score(
        self,
        product_data: Dict,
        ad_data: Dict,
        correlations: List[Dict]
    ) -> float:
        """
        Calculate overall business health score (0-100)

        Factors:
        - Revenue trend: 30%
        - ROAS: 25%
        - Product performance: 25%
        - Critical issues: -20%
        """
        score = 100.0

        # Deduct for low ROAS
        avg_roas = ad_data.get("avg_roas", 0)
        if avg_roas < 2.0:
            score -= (2.0 - avg_roas) * 10

        # Deduct for critical issues
        critical_count = len([c for c in correlations if c.get("severity") == "high"])
        score -= critical_count * 10

        # Deduct for underperformers
        underperformer_count = len(product_data.get("underperformers", []))
        score -= min(underperformer_count * 2, 20)

        return max(0, min(100, score))

    def invalidate_cache(self, user_id: Optional[int] = None, store_id: Optional[int] = None):
        """Invalidate cache for specific user/store"""
        cache_key = f"context_{user_id}_{store_id}"
        if cache_key in self._cache:
            del self._cache[cache_key]
            del self._cache_timestamp[cache_key]
            logger.info(f"Cache invalidated for {cache_key}")


# Singleton instance
_unified_context_builder = None


def get_unified_context_builder(db: Session) -> UnifiedContextBuilder:
    """Get or create unified context builder instance"""
    global _unified_context_builder
    if _unified_context_builder is None:
        _unified_context_builder = UnifiedContextBuilder(db)
    return _unified_context_builder
