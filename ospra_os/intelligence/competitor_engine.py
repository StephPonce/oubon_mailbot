"""
Competitor Intelligence Engine - Central orchestration for competitive analysis

Integrates:
- Competitor scraping and tracking
- Price monitoring and analysis
- Market share estimation
- Gap analysis
- Ad intelligence

Author: OspraOS
Date: November 2025
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from ospra_os.intelligence.competitor_scraper import CompetitorScraper
from ospra_os.intelligence.price_tracker import PriceTracker
from ospra_os.intelligence.market_share_estimator import MarketShareEstimator
from ospra_os.intelligence.gap_analyzer import GapAnalyzer
from ospra_os.intelligence.ad_intelligence import AdIntelligence

logger = logging.getLogger(__name__)


class CompetitorIntelligenceEngine:
    """
    Central engine for competitive intelligence

    Orchestrates all competitor tracking and analysis
    """

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.scraper = CompetitorScraper()
        self.price_tracker = PriceTracker(db_session)
        self.market_estimator = MarketShareEstimator(db_session)
        self.gap_analyzer = GapAnalyzer(db_session)
        self.ad_intelligence = AdIntelligence(db_session)

    # ========================================================================
    # COMPETITOR MANAGEMENT
    # ========================================================================

    async def add_competitor(
        self,
        url: str,
        name: Optional[str] = None,
        competitor_type: str = 'DIRECT',
        threat_level: str = 'MEDIUM',
        priority: int = 5,
        primary_niches: Optional[List[str]] = None
    ) -> dict:
        """
        Add new competitor to track

        Args:
            url: Store URL
            name: Competitor name (auto-detected if None)
            competitor_type: DIRECT, INDIRECT, MARKET_LEADER, EMERGING
            threat_level: HIGH, MEDIUM, LOW
            priority: 1-10 scale
            primary_niches: List of niche tags

        Returns:
            Created competitor dict
        """
        from ospra_os.models.competitor import Competitor

        # Detect platform and get store info
        platform = await self.scraper.detect_platform(url)
        store_info = await self.scraper.get_store_info(url)

        # Use provided name or detected name
        competitor_name = name or store_info.get('store_name', url)

        # Generate ID
        competitor_id = f"comp_{uuid.uuid4().hex[:12]}"

        # Create competitor record
        competitor = Competitor(
            competitor_id=competitor_id,
            name=competitor_name,
            store_url=url,
            platform=platform,
            status='ACTIVE',
            competitor_type=competitor_type,
            threat_level=threat_level,
            priority=priority,
            primary_niches=primary_niches or [],
            first_tracked=datetime.utcnow().date(),
            social_profiles=store_info.get('social_links', {}),
            created_at=datetime.utcnow()
        )

        self.db.add(competitor)
        await self.db.commit()
        await self.db.refresh(competitor)

        logger.info(f"Added competitor: {competitor_name} ({competitor_id})")

        # Kick off initial scrape in background
        try:
            await self.track_competitor_products(competitor_id)
        except Exception as e:
            logger.error(f"Error in initial product scrape: {e}")

        return self._competitor_to_dict(competitor)

    async def get_competitor(self, competitor_id: str) -> Optional[dict]:
        """
        Get full competitor profile with analysis

        Args:
            competitor_id: Competitor ID

        Returns:
            Complete competitor profile dict or None
        """
        from ospra_os.models.competitor import Competitor

        query = select(Competitor).where(Competitor.competitor_id == competitor_id)
        result = await self.db.execute(query)
        competitor = result.scalar_one_or_none()

        if not competitor:
            return None

        # Build comprehensive profile
        profile = self._competitor_to_dict(competitor)

        # Add analysis data
        profile['revenue_estimate'] = await self.market_estimator.estimate_competitor_revenue(competitor_id)
        profile['ad_analysis'] = await self.ad_intelligence.get_ad_creative_analysis(competitor_id)

        # Recent activity
        recent_activity = await self.get_recent_activity(days=30, competitor_id=competitor_id)
        profile['recent_activity'] = recent_activity[:10]  # Last 10 activities

        return profile

    async def list_competitors(
        self,
        sort_by: str = 'threat_level',
        competitor_type: Optional[str] = None,
        threat_level: Optional[str] = None,
        status: str = 'ACTIVE'
    ) -> List[dict]:
        """
        List all tracked competitors

        Args:
            sort_by: Sort field (threat_level, name, revenue, priority)
            competitor_type: Filter by type
            threat_level: Filter by threat level
            status: Filter by status

        Returns:
            List of competitor dicts
        """
        from ospra_os.models.competitor import Competitor

        query = select(Competitor)

        # Filters
        if status:
            query = query.where(Competitor.status == status)
        if competitor_type:
            query = query.where(Competitor.competitor_type == competitor_type)
        if threat_level:
            query = query.where(Competitor.threat_level == threat_level)

        # Sorting
        if sort_by == 'threat_level':
            # Custom sort: HIGH, MEDIUM, LOW
            query = query.order_by(
                desc(Competitor.threat_level == 'HIGH'),
                desc(Competitor.threat_level == 'MEDIUM'),
                Competitor.name
            )
        elif sort_by == 'revenue':
            query = query.order_by(desc(Competitor.estimated_revenue))
        elif sort_by == 'priority':
            query = query.order_by(Competitor.priority)
        else:  # name
            query = query.order_by(Competitor.name)

        result = await self.db.execute(query)
        competitors = result.scalars().all()

        return [self._competitor_to_dict(c) for c in competitors]

    async def update_competitor(self, competitor_id: str) -> dict:
        """
        Refresh competitor data by re-scraping

        Args:
            competitor_id: Competitor ID

        Returns:
            Updated competitor dict
        """
        from ospra_os.models.competitor import Competitor

        query = select(Competitor).where(Competitor.competitor_id == competitor_id)
        result = await self.db.execute(query)
        competitor = result.scalar_one_or_none()

        if not competitor:
            return {'error': 'Competitor not found'}

        # Re-scrape products
        await self.track_competitor_products(competitor_id)

        # Update last_scraped timestamp
        competitor.last_scraped = datetime.utcnow()
        await self.db.commit()

        logger.info(f"Updated competitor: {competitor.name}")

        return self._competitor_to_dict(competitor)

    async def remove_competitor(self, competitor_id: str):
        """
        Stop tracking a competitor (soft delete)

        Args:
            competitor_id: Competitor ID
        """
        from ospra_os.models.competitor import Competitor

        query = select(Competitor).where(Competitor.competitor_id == competitor_id)
        result = await self.db.execute(query)
        competitor = result.scalar_one_or_none()

        if competitor:
            competitor.status = 'REMOVED'
            await self.db.commit()
            logger.info(f"Removed competitor: {competitor.name}")

    # ========================================================================
    # PRODUCT TRACKING
    # ========================================================================

    async def track_competitor_products(self, competitor_id: str) -> List[dict]:
        """
        Scrape and track all products from a competitor

        Args:
            competitor_id: Competitor ID

        Returns:
            List of tracked products
        """
        from ospra_os.models.competitor import Competitor, CompetitorProduct, CompetitorScrapeLogs

        # Get competitor
        query = select(Competitor).where(Competitor.competitor_id == competitor_id)
        result = await self.db.execute(query)
        competitor = result.scalar_one_or_none()

        if not competitor:
            return []

        # Start scrape log
        log_id = f"log_{uuid.uuid4().hex[:12]}"
        scrape_log = CompetitorScrapeLogs(
            log_id=log_id,
            competitor_id=competitor_id,
            scrape_started_at=datetime.utcnow(),
            status='IN_PROGRESS'
        )
        self.db.add(scrape_log)
        await self.db.commit()

        try:
            # Scrape products
            products = await self.scraper.scrape_all_products(competitor.store_url)

            # Track products
            products_new = 0
            products_updated = 0
            price_changes = 0

            for product_data in products:
                result = await self._save_competitor_product(competitor_id, product_data)
                if result['status'] == 'new':
                    products_new += 1
                elif result['status'] == 'updated':
                    products_updated += 1
                if result.get('price_changed'):
                    price_changes += 1

            # Update scrape log
            scrape_log.scrape_completed_at = datetime.utcnow()
            scrape_log.duration_seconds = int((scrape_log.scrape_completed_at - scrape_log.scrape_started_at).total_seconds())
            scrape_log.status = 'SUCCESS'
            scrape_log.products_found = len(products)
            scrape_log.products_new = products_new
            scrape_log.products_updated = products_updated
            scrape_log.price_changes = price_changes

            # Update competitor stats
            competitor.total_tracked_products = len(products)
            competitor.last_scraped = datetime.utcnow()

            await self.db.commit()

            logger.info(f"Tracked {len(products)} products for {competitor.name} ({products_new} new, {products_updated} updated)")

            return products

        except Exception as e:
            scrape_log.status = 'FAILED'
            scrape_log.error_message = str(e)
            await self.db.commit()
            logger.error(f"Error tracking competitor products: {e}")
            return []

    async def _save_competitor_product(self, competitor_id: str, product_data: dict) -> dict:
        """Save or update competitor product"""
        from ospra_os.models.competitor import CompetitorProduct

        # Generate product ID
        product_url = product_data.get('url', '')
        product_id = f"cprod_{uuid.uuid4().hex[:12]}"

        # Check if product already exists (by URL or Shopify ID)
        query = select(CompetitorProduct).where(
            and_(
                CompetitorProduct.competitor_id == competitor_id,
                CompetitorProduct.url == product_url
            )
        )
        result = await self.db.execute(query)
        existing = result.scalar_one_or_none()

        price_changed = False

        if existing:
            # Update existing product
            old_price = existing.current_price
            new_price = product_data.get('price')

            if old_price and new_price and old_price != new_price:
                price_changed = True
                existing.last_price_change = datetime.utcnow()

                # Calculate price drop
                if new_price < old_price:
                    existing.price_dropped = True
                    existing.price_drop_percent = ((old_price - new_price) / old_price) * 100
                else:
                    existing.price_dropped = False
                    existing.price_drop_percent = 0

                # Record price history
                await self.price_tracker.record_price(
                    product_id=existing.product_id,
                    price=new_price,
                    competitor_id=competitor_id,
                    original_price=product_data.get('original_price'),
                    in_stock=product_data.get('available', True)
                )

            # Update fields
            existing.name = product_data.get('name')
            existing.current_price = new_price
            existing.original_price = product_data.get('original_price')
            existing.discount_percent = product_data.get('discount_percent', 0)
            existing.image_url = product_data.get('image_url')
            existing.in_stock = product_data.get('available', True)
            existing.last_seen = datetime.utcnow()
            existing.last_checked = datetime.utcnow()

            await self.db.commit()

            return {'status': 'updated', 'price_changed': price_changed, 'product_id': existing.product_id}

        else:
            # Create new product
            product = CompetitorProduct(
                product_id=product_id,
                competitor_id=competitor_id,
                name=product_data.get('name'),
                url=product_url,
                image_url=product_data.get('image_url'),
                category=product_data.get('product_type'),
                sku=product_data.get('sku'),
                handle=product_data.get('handle'),
                description=product_data.get('description'),
                vendor=product_data.get('vendor'),
                product_type=product_data.get('product_type'),
                tags=product_data.get('tags', []),
                current_price=product_data.get('price'),
                original_price=product_data.get('original_price'),
                discount_percent=product_data.get('discount_percent', 0),
                in_stock=product_data.get('available', True),
                variants_count=product_data.get('variants_count', 1),
                variants_data=product_data.get('variants_data'),
                shopify_product_id=product_data.get('shopify_product_id'),
                shopify_created_at=product_data.get('shopify_created_at'),
                shopify_updated_at=product_data.get('shopify_updated_at'),
                is_new=True,
                first_seen=datetime.utcnow(),
                last_seen=datetime.utcnow(),
                created_at=datetime.utcnow()
            )

            self.db.add(product)
            await self.db.commit()

            # Record initial price
            if product.current_price:
                await self.price_tracker.record_price(
                    product_id=product_id,
                    price=product.current_price,
                    competitor_id=competitor_id,
                    original_price=product.original_price,
                    in_stock=product.in_stock
                )

            # Log activity
            await self._log_activity(
                competitor_id=competitor_id,
                activity_type='NEW_PRODUCT',
                title=f"New product added: {product.name}",
                product_id=product_id,
                product_name=product.name,
                severity='LOW',
                is_alert=False
            )

            return {'status': 'new', 'price_changed': False, 'product_id': product_id}

    async def get_competitor_products(
        self,
        competitor_id: str,
        category: Optional[str] = None,
        in_stock_only: bool = False
    ) -> List[dict]:
        """Get all products for a competitor"""
        from ospra_os.models.competitor import CompetitorProduct

        query = select(CompetitorProduct).where(
            and_(
                CompetitorProduct.competitor_id == competitor_id,
                CompetitorProduct.is_removed == False
            )
        )

        if category:
            query = query.where(CompetitorProduct.category == category)
        if in_stock_only:
            query = query.where(CompetitorProduct.in_stock == True)

        query = query.order_by(desc(CompetitorProduct.last_seen))

        result = await self.db.execute(query)
        products = result.scalars().all()

        return [self._product_to_dict(p) for p in products]

    # ========================================================================
    # ACTIVITY & ALERTS
    # ========================================================================

    async def _log_activity(
        self,
        competitor_id: str,
        activity_type: str,
        title: str,
        description: Optional[str] = None,
        product_id: Optional[str] = None,
        product_name: Optional[str] = None,
        severity: str = 'LOW',
        is_alert: bool = False,
        **kwargs
    ):
        """Log competitor activity"""
        from ospra_os.models.competitor import CompetitorActivity

        activity_id = f"act_{uuid.uuid4().hex[:12]}"

        activity = CompetitorActivity(
            activity_id=activity_id,
            competitor_id=competitor_id,
            activity_type=activity_type,
            activity_date=datetime.utcnow(),
            title=title,
            description=description,
            product_id=product_id,
            product_name=product_name,
            severity=severity,
            is_alert=is_alert,
            old_value=kwargs.get('old_value'),
            new_value=kwargs.get('new_value'),
            change_amount=kwargs.get('change_amount'),
            change_percent=kwargs.get('change_percent'),
            details=kwargs.get('details', {})
        )

        self.db.add(activity)
        await self.db.commit()

    async def get_recent_activity(
        self,
        days: int = 7,
        competitor_id: Optional[str] = None,
        activity_type: Optional[str] = None
    ) -> List[dict]:
        """Get recent competitor activity"""
        from ospra_os.models.competitor import CompetitorActivity

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        query = select(CompetitorActivity).where(
            CompetitorActivity.activity_date >= cutoff_date
        )

        if competitor_id:
            query = query.where(CompetitorActivity.competitor_id == competitor_id)
        if activity_type:
            query = query.where(CompetitorActivity.activity_type == activity_type)

        query = query.order_by(desc(CompetitorActivity.activity_date)).limit(100)

        result = await self.db.execute(query)
        activities = result.scalars().all()

        return [self._activity_to_dict(a) for a in activities]

    async def get_competitive_alerts(self, unviewed_only: bool = True) -> List[dict]:
        """Get competitive alerts"""
        from ospra_os.models.competitor import CompetitorActivity

        query = select(CompetitorActivity).where(CompetitorActivity.is_alert == True)

        if unviewed_only:
            query = query.where(CompetitorActivity.viewed == False)

        query = query.order_by(desc(CompetitorActivity.severity), desc(CompetitorActivity.activity_date))

        result = await self.db.execute(query)
        alerts = result.scalars().all()

        return [self._activity_to_dict(a) for a in alerts]

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _competitor_to_dict(self, competitor) -> dict:
        """Convert Competitor model to dict"""
        return {
            'competitor_id': competitor.competitor_id,
            'name': competitor.name,
            'store_url': competitor.store_url,
            'platform': competitor.platform,
            'status': competitor.status,
            'competitor_type': competitor.competitor_type,
            'threat_level': competitor.threat_level,
            'priority': competitor.priority,
            'estimated_revenue': competitor.estimated_revenue,
            'estimated_product_count': competitor.estimated_product_count,
            'total_tracked_products': competitor.total_tracked_products,
            'price_positioning': competitor.price_positioning,
            'primary_niches': competitor.primary_niches,
            'strengths': competitor.strengths,
            'weaknesses': competitor.weaknesses,
            'opportunities': competitor.opportunities,
            'social_profiles': competitor.social_profiles,
            'social_followers': competitor.social_followers,
            'last_scraped': competitor.last_scraped.isoformat() if competitor.last_scraped else None,
            'created_at': competitor.created_at.isoformat()
        }

    def _product_to_dict(self, product) -> dict:
        """Convert CompetitorProduct model to dict"""
        return {
            'product_id': product.product_id,
            'competitor_id': product.competitor_id,
            'name': product.name,
            'url': product.url,
            'image_url': product.image_url,
            'category': product.category,
            'current_price': product.current_price,
            'original_price': product.original_price,
            'discount_percent': product.discount_percent,
            'in_stock': product.in_stock,
            'is_new': product.is_new,
            'price_dropped': product.price_dropped,
            'price_drop_percent': product.price_drop_percent,
            'our_product_id': product.our_product_id,
            'our_price': product.our_price,
            'price_difference': product.price_difference,
            'we_are': product.we_are,
            'last_checked': product.last_checked.isoformat() if product.last_checked else None
        }

    def _activity_to_dict(self, activity) -> dict:
        """Convert CompetitorActivity model to dict"""
        return {
            'activity_id': activity.activity_id,
            'competitor_id': activity.competitor_id,
            'activity_type': activity.activity_type,
            'activity_date': activity.activity_date.isoformat(),
            'title': activity.title,
            'description': activity.description,
            'product_id': activity.product_id,
            'product_name': activity.product_name,
            'severity': activity.severity,
            'is_alert': activity.is_alert,
            'viewed': activity.viewed
        }
