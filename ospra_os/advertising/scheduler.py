"""
Ad Campaign Scheduler & Automation

Automated scheduling for campaign monitoring, budget optimization,
and performance-based adjustments across Meta, TikTok, and Google Ads.

Author: OspraOS
Date: November 2025
"""

from typing import Dict, List, Optional
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ospra_os.advertising.meta.meta_ads import MetaAdsManager
from ospra_os.advertising.tiktok.tiktok_ads import TikTokAdsManager
from ospra_os.advertising.google.google_ads import GoogleAdsManager
from ospra_os.advertising.creative_generator import AdCreativeGenerator
from ospra_os.core.settings import get_settings

logger = logging.getLogger(__name__)


class AdScheduler:
    """
    Automated ad campaign scheduler for monitoring and optimization.

    Features:
    - Daily performance checks (9 AM)
    - Budget optimization (every 6 hours)
    - Auto-pause poor performers (hourly)
    - Multi-platform campaign orchestration

    Usage:
        >>> scheduler = AdScheduler()
        >>> await scheduler.start()
    """

    # Performance thresholds
    HIGH_CTR_THRESHOLD = 0.02  # 2%
    LOW_CTR_THRESHOLD = 0.005  # 0.5%
    HIGH_ROAS_THRESHOLD = 3.0  # 3:1 return
    LOW_ROAS_THRESHOLD = 1.0   # 1:1 return
    BUDGET_ADJUSTMENT_PERCENT = 0.20  # 20% increase/decrease

    def __init__(self):
        """Initialize the ad scheduler."""
        self.scheduler = AsyncIOScheduler()
        self.settings = get_settings()

        # Initialize platform managers
        try:
            self.meta_manager = MetaAdsManager()
        except Exception as e:
            logger.warning(f"Meta Ads not available: {e}")
            self.meta_manager = None

        try:
            self.tiktok_manager = TikTokAdsManager()
        except Exception as e:
            logger.warning(f"TikTok Ads not available: {e}")
            self.tiktok_manager = None

        try:
            self.google_manager = GoogleAdsManager()
        except Exception as e:
            logger.warning(f"Google Ads not available: {e}")
            self.google_manager = None

        # Creative generator
        try:
            self.creative_generator = AdCreativeGenerator()
        except Exception as e:
            logger.warning(f"Creative generator not available: {e}")
            self.creative_generator = None

        # Campaign tracking
        self.active_campaigns: Dict[str, Dict] = {}

    async def start(self):
        """Start the scheduler with all automation jobs."""
        logger.info("🚀 Starting Ad Automation Scheduler")

        # Daily performance check at 9 AM
        self.scheduler.add_job(
            self.daily_performance_check,
            CronTrigger(hour=9, minute=0),
            id='daily_performance_check',
            name='Daily Performance Check',
            replace_existing=True
        )
        logger.info("✅ Scheduled: Daily performance check at 9:00 AM")

        # Budget optimization every 6 hours
        self.scheduler.add_job(
            self.optimize_budgets,
            IntervalTrigger(hours=6),
            id='budget_optimization',
            name='Budget Optimization',
            replace_existing=True
        )
        logger.info("✅ Scheduled: Budget optimization every 6 hours")

        # Auto-pause poor performers every hour
        self.scheduler.add_job(
            self.auto_pause_poor_performers,
            IntervalTrigger(hours=1),
            id='auto_pause',
            name='Auto-Pause Poor Performers',
            replace_existing=True
        )
        logger.info("✅ Scheduled: Auto-pause check every hour")

        # Start scheduler
        self.scheduler.start()
        logger.info("🎯 Ad Scheduler is now running")

    async def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("⏹️  Ad Scheduler stopped")

    async def create_multi_platform_campaign(
        self,
        product_id: int,
        product_name: str,
        product_description: str,
        product_url: str,
        image_url: Optional[str] = None,
        video_id: Optional[str] = None,
        platforms: List[str] = None,
        daily_budget: float = 15.0,
        target_audience: Optional[Dict] = None,
        auto_launch: bool = False
    ) -> Dict:
        """
        Create campaigns across multiple platforms for a product.

        Args:
            product_id: Internal product ID
            product_name: Product name
            product_description: Product description
            product_url: Landing page URL
            image_url: Product image URL (for Meta/TikTok)
            video_id: Video ID (for TikTok)
            platforms: List of platforms ['meta', 'tiktok', 'google']
            daily_budget: Budget per platform per day
            target_audience: Targeting parameters
            auto_launch: Whether to activate campaigns immediately

        Returns:
            Dict with campaign IDs and status for each platform
        """
        if not platforms:
            platforms = ['meta', 'tiktok', 'google']

        logger.info(f"🎬 Creating multi-platform campaigns for: {product_name}")
        logger.info(f"📊 Platforms: {', '.join(platforms)}")

        results = {
            'product_id': product_id,
            'product_name': product_name,
            'campaigns': {},
            'created_at': datetime.utcnow().isoformat(),
            'status': 'pending'
        }

        # Generate AI creatives for each platform
        for platform in platforms:
            try:
                logger.info(f"🎨 Generating creative for {platform}...")

                # Generate ad copy
                if self.creative_generator:
                    creative = await self.creative_generator.generate_ad_copy(
                        platform=platform,
                        product_name=product_name,
                        product_description=product_description,
                        variations=1
                    )
                    ad_copy = creative['variations'][0]
                else:
                    # Fallback to simple copy
                    ad_copy = {
                        'headline': f"Discover {product_name}",
                        'body': product_description[:100],
                        'cta': 'Shop Now'
                    }

                # Create campaign on platform
                campaign_result = await self._create_platform_campaign(
                    platform=platform,
                    product_name=product_name,
                    product_url=product_url,
                    ad_copy=ad_copy,
                    image_url=image_url,
                    video_id=video_id,
                    daily_budget=daily_budget,
                    target_audience=target_audience
                )

                results['campaigns'][platform] = campaign_result

                # Track campaign
                if campaign_result.get('success'):
                    campaign_key = f"{platform}_{campaign_result['campaign_id']}"
                    self.active_campaigns[campaign_key] = {
                        'product_id': product_id,
                        'platform': platform,
                        'campaign_id': campaign_result['campaign_id'],
                        'daily_budget': daily_budget,
                        'status': 'paused' if not auto_launch else 'active',
                        'created_at': datetime.utcnow()
                    }

                logger.info(f"✅ {platform} campaign created: {campaign_result['campaign_id']}")

            except Exception as e:
                logger.error(f"❌ Failed to create {platform} campaign: {e}")
                results['campaigns'][platform] = {
                    'success': False,
                    'error': str(e)
                }

        # Overall status
        successful = sum(1 for c in results['campaigns'].values() if c.get('success'))
        results['status'] = 'success' if successful > 0 else 'failed'
        results['successful_platforms'] = successful
        results['total_platforms'] = len(platforms)

        logger.info(f"🎉 Campaign creation complete: {successful}/{len(platforms)} platforms successful")

        return results

    async def _create_platform_campaign(
        self,
        platform: str,
        product_name: str,
        product_url: str,
        ad_copy: Dict,
        image_url: Optional[str],
        video_id: Optional[str],
        daily_budget: float,
        target_audience: Optional[Dict]
    ) -> Dict:
        """Create campaign on a specific platform."""
        if platform == 'meta' and self.meta_manager:
            return await self.meta_manager.create_product_campaign(
                product_name=product_name,
                product_url=product_url,
                image_url=image_url,
                ad_copy=ad_copy.get('body', ''),
                daily_budget=daily_budget,
                target_audience=target_audience
            )

        elif platform == 'tiktok' and self.tiktok_manager:
            return await self.tiktok_manager.create_product_campaign(
                product_name=product_name,
                product_url=product_url,
                video_id=video_id or '',
                ad_text=ad_copy.get('body', ''),
                daily_budget=daily_budget
            )

        elif platform == 'google' and self.google_manager:
            # Google needs keywords - extract from product name/description
            keywords = self._generate_keywords(product_name)

            # Get Google-specific copy
            google_copy = ad_copy.get('descriptions', [ad_copy.get('body', '')])[0]

            return await self.google_manager.create_product_campaign(
                product_name=product_name,
                product_url=product_url,
                keywords=keywords,
                ad_copy=google_copy,
                daily_budget=daily_budget
            )

        else:
            return {
                'success': False,
                'error': f'{platform} manager not available'
            }

    def _generate_keywords(self, product_name: str) -> List[str]:
        """Generate basic keywords from product name."""
        words = product_name.lower().split()
        keywords = [
            product_name.lower(),
            f"buy {product_name.lower()}",
            f"{product_name.lower()} online",
            f"best {product_name.lower()}"
        ]
        return keywords

    async def daily_performance_check(self):
        """
        Daily performance check job (runs at 9 AM).

        Reviews all active campaigns and generates performance report.
        """
        logger.info("📊 Running daily performance check...")

        report = {
            'date': datetime.utcnow().isoformat(),
            'campaigns_checked': 0,
            'platforms': {
                'meta': [],
                'tiktok': [],
                'google': []
            },
            'summary': {}
        }

        # Check each active campaign
        for campaign_key, campaign_data in self.active_campaigns.items():
            platform = campaign_data['platform']
            campaign_id = campaign_data['campaign_id']

            try:
                metrics = await self._get_campaign_metrics(platform, campaign_id)

                if metrics:
                    report['platforms'][platform].append({
                        'campaign_id': campaign_id,
                        'product_id': campaign_data['product_id'],
                        'metrics': metrics
                    })
                    report['campaigns_checked'] += 1

            except Exception as e:
                logger.error(f"Error checking {platform} campaign {campaign_id}: {e}")

        # Generate summary
        total_spend = 0
        total_impressions = 0
        total_clicks = 0

        for platform_campaigns in report['platforms'].values():
            for campaign in platform_campaigns:
                metrics = campaign['metrics']
                total_spend += metrics.get('spend', 0)
                total_impressions += metrics.get('impressions', 0)
                total_clicks += metrics.get('clicks', 0)

        report['summary'] = {
            'total_spend': round(total_spend, 2),
            'total_impressions': total_impressions,
            'total_clicks': total_clicks,
            'average_ctr': round(total_clicks / total_impressions * 100, 2) if total_impressions > 0 else 0
        }

        logger.info(f"✅ Daily check complete: {report['campaigns_checked']} campaigns")
        logger.info(f"💰 Total spend: ${report['summary']['total_spend']}")
        logger.info(f"📈 Total clicks: {report['summary']['total_clicks']}")

        return report

    async def optimize_budgets(self):
        """
        Budget optimization job (runs every 6 hours).

        Adjusts budgets based on performance:
        - High CTR (>2%) → Increase budget by 20%
        - Low CTR (<0.5%) → Decrease budget by 20%
        """
        logger.info("💰 Running budget optimization...")

        optimized_count = 0

        for campaign_key, campaign_data in self.active_campaigns.items():
            if campaign_data['status'] != 'active':
                continue

            platform = campaign_data['platform']
            campaign_id = campaign_data['campaign_id']
            current_budget = campaign_data['daily_budget']

            try:
                # Get performance metrics
                metrics = await self._get_campaign_metrics(platform, campaign_id)

                if not metrics:
                    continue

                ctr = metrics.get('ctr', 0)
                spend = metrics.get('spend', 0)

                # Optimization logic
                new_budget = current_budget

                if ctr >= self.HIGH_CTR_THRESHOLD:
                    # High performer - increase budget
                    new_budget = current_budget * (1 + self.BUDGET_ADJUSTMENT_PERCENT)
                    logger.info(f"📈 {platform} {campaign_id}: High CTR {ctr:.2%} → Increase budget ${current_budget:.2f} → ${new_budget:.2f}")

                elif ctr <= self.LOW_CTR_THRESHOLD and spend > current_budget * 0.5:
                    # Low performer with significant spend - decrease budget
                    new_budget = current_budget * (1 - self.BUDGET_ADJUSTMENT_PERCENT)
                    logger.info(f"📉 {platform} {campaign_id}: Low CTR {ctr:.2%} → Decrease budget ${current_budget:.2f} → ${new_budget:.2f}")

                # Apply budget change if different
                if abs(new_budget - current_budget) > 0.01:
                    # Update budget on platform (would need platform-specific implementation)
                    campaign_data['daily_budget'] = new_budget
                    optimized_count += 1

            except Exception as e:
                logger.error(f"Error optimizing {platform} campaign {campaign_id}: {e}")

        logger.info(f"✅ Budget optimization complete: {optimized_count} campaigns adjusted")

    async def auto_pause_poor_performers(self):
        """
        Auto-pause job (runs hourly).

        Pauses campaigns with:
        - CTR < 0.5% after 100+ impressions
        - ROAS < 1.0 after 10+ conversions
        """
        logger.info("⏸️  Checking for poor performers...")

        paused_count = 0
        MIN_IMPRESSIONS_THRESHOLD = 100
        MIN_CONVERSIONS_THRESHOLD = 10

        for campaign_key, campaign_data in self.active_campaigns.items():
            if campaign_data['status'] != 'active':
                continue

            platform = campaign_data['platform']
            campaign_id = campaign_data['campaign_id']

            try:
                metrics = await self._get_campaign_metrics(platform, campaign_id)

                if not metrics:
                    continue

                impressions = metrics.get('impressions', 0)
                ctr = metrics.get('ctr', 0)
                conversions = metrics.get('conversions', 0)
                roas = metrics.get('roas', 0)

                should_pause = False
                pause_reason = ""

                # Check CTR after minimum impressions
                if impressions >= MIN_IMPRESSIONS_THRESHOLD:
                    if ctr < self.LOW_CTR_THRESHOLD:
                        should_pause = True
                        pause_reason = f"Low CTR ({ctr:.2%}) after {impressions} impressions"

                # Check ROAS after minimum conversions
                if conversions >= MIN_CONVERSIONS_THRESHOLD:
                    if roas < self.LOW_ROAS_THRESHOLD:
                        should_pause = True
                        pause_reason = f"Low ROAS ({roas:.2f}) after {conversions} conversions"

                if should_pause:
                    logger.warning(f"⏸️  Pausing {platform} {campaign_id}: {pause_reason}")

                    # Pause campaign on platform
                    await self._pause_campaign(platform, campaign_id)

                    # Update tracking
                    campaign_data['status'] = 'paused'
                    campaign_data['pause_reason'] = pause_reason
                    campaign_data['paused_at'] = datetime.utcnow()

                    paused_count += 1

            except Exception as e:
                logger.error(f"Error checking {platform} campaign {campaign_id}: {e}")

        if paused_count > 0:
            logger.info(f"⏸️  Auto-paused {paused_count} poor performing campaigns")
        else:
            logger.info("✅ No campaigns needed pausing")

    async def _get_campaign_metrics(self, platform: str, campaign_id: str) -> Optional[Dict]:
        """Get metrics for a campaign from the appropriate platform."""
        try:
            if platform == 'meta' and self.meta_manager:
                return await self.meta_manager.get_campaign_metrics(campaign_id)
            elif platform == 'tiktok' and self.tiktok_manager:
                return await self.tiktok_manager.get_campaign_metrics(campaign_id)
            elif platform == 'google' and self.google_manager:
                return await self.google_manager.get_campaign_metrics(campaign_id)
        except Exception as e:
            logger.error(f"Error fetching metrics for {platform} {campaign_id}: {e}")

        return None

    async def _pause_campaign(self, platform: str, campaign_id: str) -> bool:
        """Pause a campaign on the appropriate platform."""
        try:
            if platform == 'meta' and self.meta_manager:
                return await self.meta_manager.pause_campaign(campaign_id)
            elif platform == 'tiktok' and self.tiktok_manager:
                return await self.tiktok_manager.pause_campaign(campaign_id)
            elif platform == 'google' and self.google_manager:
                return await self.google_manager.pause_campaign(campaign_id)
        except Exception as e:
            logger.error(f"Error pausing {platform} campaign {campaign_id}: {e}")

        return False

    async def activate_campaign(self, platform: str, campaign_id: str) -> bool:
        """Manually activate a paused campaign."""
        try:
            success = False

            if platform == 'meta' and self.meta_manager:
                success = await self.meta_manager.activate_campaign(campaign_id)
            elif platform == 'tiktok' and self.tiktok_manager:
                success = await self.tiktok_manager.activate_campaign(campaign_id)
            elif platform == 'google' and self.google_manager:
                success = await self.google_manager.activate_campaign(campaign_id)

            if success:
                # Update tracking
                campaign_key = f"{platform}_{campaign_id}"
                if campaign_key in self.active_campaigns:
                    self.active_campaigns[campaign_key]['status'] = 'active'
                    self.active_campaigns[campaign_key]['activated_at'] = datetime.utcnow()

                logger.info(f"▶️  Activated {platform} campaign: {campaign_id}")

            return success

        except Exception as e:
            logger.error(f"Error activating {platform} campaign {campaign_id}: {e}")
            return False

    def get_campaign_status(self, platform: str, campaign_id: str) -> Optional[Dict]:
        """Get status of a tracked campaign."""
        campaign_key = f"{platform}_{campaign_id}"
        return self.active_campaigns.get(campaign_key)

    def get_all_campaigns(self) -> Dict:
        """Get all tracked campaigns with their status."""
        return {
            'total_campaigns': len(self.active_campaigns),
            'active': sum(1 for c in self.active_campaigns.values() if c['status'] == 'active'),
            'paused': sum(1 for c in self.active_campaigns.values() if c['status'] == 'paused'),
            'campaigns': self.active_campaigns
        }
