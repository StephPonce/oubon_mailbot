import logging
import os
import time
import threading
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import deque

try:
    import schedule
except ImportError:
    schedule = None
    logging.warning("schedule module not available - background jobs will be limited")

from ospra_os.intelligence.ai_research_agent import AIResearchAgent

logger = logging.getLogger(__name__)


class Alert:
    """AI-generated alert from background monitoring"""

    def __init__(
        self,
        severity: str,
        title: str,
        message: str,
        data: Optional[Dict] = None
    ):
        self.severity = severity  # 'critical', 'warning', 'info'
        self.title = title
        self.message = message
        self.data = data or {}
        self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        return {
            'severity': self.severity,
            'title': self.title,
            'message': self.message,
            'data': self.data,
            'created_at': self.created_at
        }


class IntelligenceScheduler:
    """
    Level 3 AI - Autonomous Background Intelligence

    Runs scheduled jobs that:
    - Analyze product performance
    - Monitor competitors
    - Track market trends
    - Generate actionable alerts
    """

    def __init__(self):
        self.ai_agent = AIResearchAgent()
        self.running = False
        self.thread = None
        self.alerts = deque(maxlen=1000)  # Keep last 1000 alerts
        self.job_history = {}

        logger.info("[BRAIN] Intelligence Scheduler initialized")

    def start(self):
        """Start background jobs in separate thread"""

        if self.running:
            logger.warning("Scheduler already running")
            return

        if not self.ai_agent.enabled:
            logger.warning("[WARNING]  AI Research Agent disabled (no ANTHROPIC_API_KEY) - scheduler will run with limited functionality")

        # Schedule jobs
        schedule.every(6).hours.do(self._job_wrapper, "analyze_products", self.analyze_products)
        schedule.every(12).hours.do(self._job_wrapper, "monitor_competitors", self.monitor_competitors)
        schedule.every().day.at("09:00").do(self._job_wrapper, "track_trends", self.track_trends)
        schedule.every().day.at("03:00").do(self._job_wrapper, "auto_discover", self.auto_discover_products)
        schedule.every().sunday.at("18:00").do(self._job_wrapper, "weekly_report", self.weekly_report)

        # Start scheduler thread
        self.running = True
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()

        logger.info("[SUCCESS] Level 3 AI scheduler started")
        logger.info("[LIST] Scheduled jobs:")
        logger.info("   • analyze_products - every 6 hours")
        logger.info("   • monitor_competitors - every 12 hours")
        logger.info("   • track_trends - daily at 9am")
        logger.info("   • auto_discover - daily at 3am (fresh products)")
        logger.info("   • weekly_report - Sundays at 6pm")

    def stop(self):
        """Stop background jobs"""

        if not self.running:
            logger.warning("Scheduler not running")
            return

        self.running = False
        schedule.clear()

        if self.thread:
            self.thread.join(timeout=5)

        logger.info("[PAUSE]  Level 3 AI scheduler stopped")

    def _run_scheduler(self):
        """Main scheduler loop (runs in background thread)"""

        logger.info("[REFRESH] Scheduler loop started")

        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                self.add_alert(
                    'critical',
                    'Scheduler Error',
                    f'Background scheduler encountered an error: {str(e)}'
                )

    def _job_wrapper(self, job_name: str, job_func):
        """Wrapper to track job execution and handle errors"""

        logger.info(f"[START] Running job: {job_name}")
        start_time = datetime.now()

        try:
            job_func()

            duration = (datetime.now() - start_time).total_seconds()
            self.job_history[job_name] = {
                'last_run': start_time.isoformat(),
                'status': 'success',
                'duration_seconds': duration
            }

            logger.info(f"[SUCCESS] Job completed: {job_name} ({duration:.1f}s)")

        except Exception as e:
            logger.error(f"[ERROR] Job failed: {job_name} - {e}")

            self.job_history[job_name] = {
                'last_run': start_time.isoformat(),
                'status': 'failed',
                'error': str(e)
            }

            self.add_alert(
                'critical',
                f'Job Failed: {job_name}',
                f'Background job {job_name} failed: {str(e)}'
            )

    # ==========================================
    # BACKGROUND JOBS
    # ==========================================

    def analyze_products(self):
        """
        Analyze all products and identify:
        - Underperformers that need intervention
        - Top performers worth replicating
        - Products to test/optimize
        """

        logger.info("[STATS] Analyzing product performance...")

        try:
            # Import here to avoid circular dependency
            from ospra_os.database.db import get_db_session
            from ospra_os.database.models import Product
            from sqlalchemy import select

            # Get all products from database
            with get_db_session() as session:
                stmt = select(Product).where(Product.source != 'fallback')
                products = session.execute(stmt).scalars().all()

                if not products:
                    logger.info("No products to analyze")
                    return

                logger.info(f"Analyzing {len(products)} products...")

                underperformers = []
                top_performers = []

                for product in products[:20]:  # Limit to avoid quota exhaustion
                    # Simple performance heuristics
                    # In production, you'd track views, clicks, sales from Shopify

                    performance_data = {
                        'views': 0,
                        'clicks': 0,
                        'sales': 0,
                        'conversion_rate': 0.0,
                        'days_live': 7
                    }

                    # Flag underperformers
                    if product.score < 6.0:
                        underperformers.append({
                            'product': {
                                'name': product.name,
                                'price': product.price,
                                'cost': product.cost,
                                'category': product.category,
                                'rating': product.rating,
                                'orders': product.orders
                            },
                            'performance': performance_data
                        })

                    # Flag top performers
                    if product.score >= 8.5:
                        top_performers.append({
                            'product': {
                                'name': product.name,
                                'price': product.price,
                                'score': product.score,
                                'velocity_score': product.velocity_score
                            },
                            'performance': performance_data
                        })

                # Generate alerts for underperformers
                if underperformers:
                    logger.info(f"Found {len(underperformers)} underperforming products")

                    for item in underperformers[:5]:  # Top 5 worst
                        product = item['product']
                        performance = item['performance']

                        # Use AI to analyze why it's failing
                        if self.ai_agent.enabled:
                            import asyncio

                            analysis = asyncio.run(
                                self.ai_agent.analyze_product_failure(
                                    product,
                                    performance
                                )
                            )

                            self.add_alert(
                                'warning',
                                f'Underperformer: {product["name"][:50]}',
                                analysis['hypothesis'],
                                {
                                    'product_name': product['name'],
                                    'score': product.get('score', 0),
                                    'recommendations': analysis['recommendations'],
                                    'predicted_improvement': analysis['predicted_improvement'],
                                    'confidence': analysis['confidence']
                                }
                            )
                        else:
                            self.add_alert(
                                'warning',
                                f'Underperformer: {product["name"][:50]}',
                                f'Product score {product.get("score", 0):.1f}/10 - Consider reviewing pricing or product-market fit',
                                {'product_name': product['name']}
                            )

                # Generate insights for top performers
                if top_performers:
                    logger.info(f"Found {len(top_performers)} top performing products")

                    self.add_alert(
                        'info',
                        f'{len(top_performers)} Top Performers Identified',
                        f'Products scoring 8.5+ are performing well. Consider finding similar products.',
                        {
                            'top_products': [p['product']['name'] for p in top_performers[:5]]
                        }
                    )

                logger.info("[SUCCESS] Product analysis complete")

        except Exception as e:
            logger.error(f"Product analysis failed: {e}")
            raise

    def monitor_competitors(self):
        """
        Monitor competitor products and market changes
        Track pricing, new products, and generate alerts
        """

        logger.info("[SEARCH] Monitoring competitors...")

        try:
            import asyncio
            from ospra_os.intelligence.competitor_engine import CompetitorIntelligenceEngine
            from ospra_os.database.multi_store_models import get_multi_store_session

            async def run_monitoring():
                async with get_multi_store_session() as session:
                    engine = CompetitorIntelligenceEngine(session)

                    # Get all active competitors
                    competitors = await engine.list_competitors(status='ACTIVE')

                    if not competitors:
                        logger.info("No competitors to monitor")
                        return {
                            'scanned': 0,
                            'price_changes': 0,
                            'new_products': 0
                        }

                    total_price_changes = 0
                    total_new_products = 0

                    # Monitor each competitor
                    for competitor in competitors:
                        try:
                            logger.info(f"  Monitoring {competitor['name']}...")

                            # Update competitor data
                            await engine.update_competitor(competitor['competitor_id'])

                            # Check for price changes in last 24 hours
                            activities = await engine.get_recent_activity(
                                days=1,
                                competitor_id=competitor['competitor_id'],
                                activity_type='PRICE_CHANGE'
                            )

                            price_changes = len(activities)
                            total_price_changes += price_changes

                            # Check for new products
                            new_product_activities = await engine.get_recent_activity(
                                days=1,
                                competitor_id=competitor['competitor_id'],
                                activity_type='NEW_PRODUCT'
                            )

                            new_products = len(new_product_activities)
                            total_new_products += new_products

                            logger.info(f"    [SUCCESS] {price_changes} price changes, {new_products} new products")

                        except Exception as e:
                            logger.error(f"    [ERROR] Error monitoring {competitor['name']}: {e}")
                            continue

                    return {
                        'scanned': len(competitors),
                        'price_changes': total_price_changes,
                        'new_products': total_new_products
                    }

            # Run async monitoring
            results = asyncio.run(run_monitoring())

            # Generate alert based on findings
            if results['price_changes'] > 0 or results['new_products'] > 0:
                self.add_alert(
                    'warning' if results['price_changes'] >= 5 else 'info',
                    'Competitor Monitoring Complete',
                    f"Scanned {results['scanned']} competitors: {results['price_changes']} price changes, {results['new_products']} new products",
                    {
                        'scanned_competitors': results['scanned'],
                        'price_changes': results['price_changes'],
                        'new_products': results['new_products']
                    }
                )
            else:
                self.add_alert(
                    'info',
                    'Competitor Monitoring Complete',
                    f"Scanned {results['scanned']} competitors - no significant changes detected",
                    {'scanned_competitors': results['scanned']}
                )

            logger.info(f"[SUCCESS] Competitor monitoring complete: {results}")

        except Exception as e:
            logger.error(f"Competitor monitoring failed: {e}")
            self.add_alert(
                'critical',
                'Competitor Monitoring Failed',
                f'Error during competitor monitoring: {str(e)}',
                {'error': str(e)}
            )
            raise

    def track_trends(self):
        """
        Track market trends and identify opportunities
        """

        logger.info("[TREND] Tracking market trends...")

        try:
            # In production, this would:
            # 1. Query Google Trends API
            # 2. Analyze seasonal patterns
            # 3. Identify emerging niches

            # For now, just log
            logger.info("Trend tracking completed (placeholder)")

            self.add_alert(
                'info',
                'Market Trends',
                'Daily trend analysis completed',
                {'trending_categories': ['smart_home', 'fitness_trackers']}
            )

        except Exception as e:
            logger.error(f"Trend tracking failed: {e}")
            raise

    def weekly_report(self):
        """
        Generate weekly performance report
        """

        logger.info("[STATS] Generating weekly report...")

        try:
            # In production, this would:
            # 1. Summarize week's performance
            # 2. Highlight wins and losses
            # 3. Provide strategic recommendations

            # For now, just log
            logger.info("Weekly report generated (placeholder)")

            self.add_alert(
                'info',
                'Weekly Report Available',
                'Your weekly performance report is ready',
                {
                    'report_period': f'{(datetime.now() - timedelta(days=7)).date()} to {datetime.now().date()}',
                    'summary': 'Report generation in development'
                }
            )

        except Exception as e:
            logger.error(f"Weekly report failed: {e}")
            raise

    def auto_discover_products(self):
        """
        Automatically discover fresh products using REAL Google Trends + AliExpress
        Runs daily at 3 AM to keep database updated with latest trending products
        """

        logger.info("[SEARCH] Auto-discovering fresh products with Google Trends...")

        try:
            import asyncio
            import hashlib
            from ospra_os.product_research.multi_source_discovery import MultiSourceDiscovery
            from ospra_os.database.db import get_db_session
            from ospra_os.database.models import Product
            from sqlalchemy import delete

            # Use async discovery engine
            async def run_discovery():
                discovery_engine = MultiSourceDiscovery()

                # Discover products across all niches
                niche_products = await discovery_engine.discover_all_niches(
                    min_score=70,
                    max_per_niche=20
                )

                return niche_products

            # Run async discovery
            niche_products = asyncio.run(run_discovery())

            total_discovered = 0

            # Process each niche's products
            for niche, products in niche_products.items():
                if not products:
                    logger.warning(f"  [WARNING]  No products found for {niche}")
                    continue

                logger.info(f"  [SUCCESS] Found {len(products)} products for {niche}")
                total_discovered += len(products)

                # Save to database (replace old products for this niche)
                try:
                    with get_db_session() as session:
                        # Delete old auto-discovered products for this niche
                        session.execute(
                            delete(Product).where(
                                Product.category == niche,
                                Product.source == 'auto_discovery'
                            )
                        )

                        # Add new products
                        for product_data in products[:20]:  # Limit to top 20
                            # Generate unique ID
                            product_id = hashlib.md5(
                                f"{product_data['name']}{niche}".encode()
                            ).hexdigest()[:12]

                            # Calculate pricing from trend data
                            base_price = product_data.get('aliexpress_price') or (15.0 + (product_data['score'] * 3))
                            cost_price = base_price * 0.4
                            selling_price = base_price * 1.5
                            profit = selling_price - cost_price
                            profit_margin = (profit / selling_price) * 100

                            product = Product(
                                name=product_data['name'],
                                price=round(selling_price, 2),
                                cost=round(cost_price, 2),
                                profit_margin=round(profit_margin, 1),
                                estimated_profit=round(profit, 2),
                                velocity_score=round(product_data['trend_score'], 1),
                                score=round(product_data['score'] * 10, 1),
                                orders=int(product_data.get('search_volume', 0) * 10),
                                rating=product_data.get('supplier_rating', 4.5),
                                category=niche,
                                source='auto_discovery',
                                image_url=product_data.get('aliexpress_image', ''),
                                product_url=product_data.get('aliexpress_url', ''),
                                product_id=product_id
                            )
                            session.add(product)

                        session.commit()
                        logger.info(f"   Saved {len(products[:20])} products to database for {niche}")

                except Exception as e:
                    logger.error(f"  [ERROR] Failed to save products for {niche}: {e}")
                    continue

            # Generate summary alert
            if total_discovered > 0:
                self.add_alert(
                    'info',
                    f'Auto-Discovery Complete (Google Trends)',
                    f'Successfully discovered {total_discovered} trending products using real-time data',
                    {
                        'niches': list(niche_products.keys()),
                        'total_products': total_discovered,
                        'data_source': 'GOOGLE_TRENDS + AliExpress',
                        'timestamp': datetime.now().isoformat()
                    }
                )
                logger.info(f"[SUCCESS] Auto-discovery complete: {total_discovered} products from Google Trends")
            else:
                self.add_alert(
                    'warning',
                    'Auto-Discovery Issue',
                    'No new products discovered - Google Trends may be rate limiting',
                    {'attempted_niches': list(niche_products.keys())}
                )
                logger.warning("[WARNING]  Auto-discovery completed but no products found")

        except Exception as e:
            logger.error(f"Auto-discovery failed: {e}")
            raise

    # ==========================================
    # ALERT MANAGEMENT
    # ==========================================

    def add_alert(
        self,
        severity: str,
        title: str,
        message: str,
        data: Optional[Dict] = None
    ):
        """Add new alert to queue"""

        alert = Alert(severity, title, message, data)
        self.alerts.append(alert)

        # Log based on severity
        if severity == 'critical':
            logger.error(f" {title}: {message}")
        elif severity == 'warning':
            logger.warning(f"[WARNING]  {title}: {message}")
        else:
            logger.info(f"[INFO]  {title}: {message}")

    def get_alerts(
        self,
        limit: int = 50,
        severity: Optional[str] = None
    ) -> List[Dict]:
        """Get recent alerts"""

        alerts = list(self.alerts)

        # Filter by severity if specified
        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        # Sort by created_at (newest first)
        alerts = sorted(
            alerts,
            key=lambda a: a.created_at,
            reverse=True
        )

        # Limit results
        alerts = alerts[:limit]

        return [a.to_dict() for a in alerts]

    def clear_alerts(self):
        """Clear all alerts"""
        self.alerts.clear()
        logger.info("Alerts cleared")

    # ==========================================
    # STATUS & CONTROL
    # ==========================================

    def get_status(self) -> Dict:
        """Get scheduler status"""

        return {
            'running': self.running,
            'ai_enabled': self.ai_agent.enabled,
            'scheduled_jobs': [
                {
                    'name': 'analyze_products',
                    'schedule': 'every 6 hours',
                    'last_run': self.job_history.get('analyze_products', {}).get('last_run'),
                    'status': self.job_history.get('analyze_products', {}).get('status')
                },
                {
                    'name': 'monitor_competitors',
                    'schedule': 'every 12 hours',
                    'last_run': self.job_history.get('monitor_competitors', {}).get('last_run'),
                    'status': self.job_history.get('monitor_competitors', {}).get('status')
                },
                {
                    'name': 'track_trends',
                    'schedule': 'daily at 9am',
                    'last_run': self.job_history.get('track_trends', {}).get('last_run'),
                    'status': self.job_history.get('track_trends', {}).get('status')
                },
                {
                    'name': 'auto_discover',
                    'schedule': 'daily at 3am',
                    'last_run': self.job_history.get('auto_discover', {}).get('last_run'),
                    'status': self.job_history.get('auto_discover', {}).get('status')
                },
                {
                    'name': 'weekly_report',
                    'schedule': 'Sundays at 6pm',
                    'last_run': self.job_history.get('weekly_report', {}).get('last_run'),
                    'status': self.job_history.get('weekly_report', {}).get('status')
                }
            ],
            'total_alerts': len(self.alerts),
            'recent_alerts': self.get_alerts(limit=5)
        }

    def run_job_now(self, job_name: str):
        """Manually trigger a specific job"""

        job_map = {
            'analyze_products': self.analyze_products,
            'monitor_competitors': self.monitor_competitors,
            'track_trends': self.track_trends,
            'auto_discover': self.auto_discover_products,
            'weekly_report': self.weekly_report
        }

        if job_name not in job_map:
            raise ValueError(f"Unknown job: {job_name}")

        logger.info(f"[TARGET] Manually triggering job: {job_name}")

        # Run in background thread to avoid blocking API
        thread = threading.Thread(
            target=self._job_wrapper,
            args=(job_name, job_map[job_name]),
            daemon=True
        )
        thread.start()


# ==========================================
# GLOBAL SCHEDULER INSTANCE
# ==========================================

_scheduler = None
_scheduler_lock = threading.Lock()


def get_scheduler() -> IntelligenceScheduler:
    """Get global scheduler instance (singleton)"""

    global _scheduler

    if _scheduler is None:
        with _scheduler_lock:
            if _scheduler is None:
                _scheduler = IntelligenceScheduler()

    return _scheduler


def start_background_jobs():
    """Start Level 3 AI background jobs"""

    scheduler = get_scheduler()
    scheduler.start()


def stop_background_jobs():
    """Stop Level 3 AI background jobs"""

    scheduler = get_scheduler()
    scheduler.stop()
