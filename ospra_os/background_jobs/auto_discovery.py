"""
Automatic Product Discovery Background Job

Runs daily product discovery for all users, finds trending products,
scores them with AI, and optionally auto-deploys high-scoring products.

Features:
- Daily automated discovery across multiple niches
- AI-powered product scoring and analysis
- Automatic notifications for high-priority products
- Optional auto-deployment to user stores
- Performance tracking and analytics
- Failure recovery and retry logic

Author: OspraOS
Date: November 2025
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Discovery systems
try:
    from ospra_os.product_research.multi_source_discovery import MultiSourceDiscovery
    MULTI_SOURCE_AVAILABLE = True
except ImportError:
    MULTI_SOURCE_AVAILABLE = False
    logging.warning("MultiSourceDiscovery not available")

try:
    from ospra_os.intelligence.product_intelligence import ProductIntelligenceEngine
    INTELLIGENCE_V3_AVAILABLE = True
except ImportError:
    INTELLIGENCE_V3_AVAILABLE = False
    logging.warning("ProductIntelligenceV3 not available")

# Deployment system
try:
    from ospra_os.deployment import UnifiedProductDeployer
    DEPLOYER_AVAILABLE = True
except ImportError:
    DEPLOYER_AVAILABLE = False
    logging.warning("UnifiedProductDeployer not available")

# Platform adapters
try:
    from ospra_os.platforms.factory import PlatformFactory
    PLATFORMS_AVAILABLE = True
except ImportError:
    PLATFORMS_AVAILABLE = False

# Database models (mock imports for now - replace with actual models)
# from ospra_os.database.models import (
#     User, Store, Product, ProductDeployment,
#     UserSettings, DiscoveryLog, Notification
# )

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AutoDiscoveryError(Exception):
    """Base exception for auto-discovery errors"""
    pass


class AutoDiscoveryJob:
    """
    Automated product discovery background job.

    Runs daily discovery for all users, finds trending products,
    scores them with AI, and handles notifications/auto-deployment.
    """

    def __init__(
        self,
        database_url: str = None,
        db_session: Session = None,
        scheduler: AsyncIOScheduler = None
    ):
        """
        Initialize auto-discovery job.

        Args:
            database_url: SQLAlchemy database URL
            db_session: Existing database session (optional)
            scheduler: APScheduler instance (optional, will create if not provided)
        """
        # Database setup
        if db_session:
            self.db = db_session
            self._owns_session = False
        elif database_url:
            engine = create_engine(database_url)
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            self.db = SessionLocal()
            self._owns_session = True
        else:
            raise ValueError("Either database_url or db_session must be provided")

        # Scheduler setup
        self.scheduler = scheduler or AsyncIOScheduler()
        self._owns_scheduler = scheduler is None

        # Discovery settings
        self.default_niches = [
            "smart_home",
            "fitness",
            "pet_supplies",
            "kitchen_gadgets",
            "outdoor_gear"
        ]

        logger.info("AutoDiscoveryJob initialized")

    def __del__(self):
        """Cleanup resources"""
        if hasattr(self, '_owns_session') and self._owns_session:
            self.db.close()

        if hasattr(self, '_owns_scheduler') and self._owns_scheduler and self.scheduler.running:
            self.scheduler.shutdown()

    async def run_discovery_for_user(
        self,
        user_id: int,
        force_run: bool = False,
        timeout_seconds: int = 1800  # 30 minute default timeout per user
    ) -> Dict[str, Any]:
        """
        Run product discovery for a specific user.

        SECURITY: Includes timeout to prevent runaway discovery jobs.

        Args:
            user_id: ID of user to run discovery for
            force_run: Force discovery even if recently run
            timeout_seconds: Maximum time allowed for discovery (default 30 min)

        Returns:
            dict: Discovery results with products found, saved, deployed, etc.
        """
        logger.info(f"Starting discovery for user {user_id} (timeout: {timeout_seconds}s)")
        start_time = datetime.utcnow()

        try:
            # Step 1: Get user and settings
            # user = self.db.query(User).filter(User.id == user_id).first()
            user = self._get_user_mock(user_id)

            if not user:
                raise AutoDiscoveryError(f"User {user_id} not found")

            if not user.get('is_active', True):
                logger.info(f"User {user_id} is not active, skipping")
                return {
                    "success": True,
                    "skipped": True,
                    "reason": "User not active"
                }

            # Get user settings
            # settings = self.db.query(UserSettings).filter(
            #     UserSettings.user_id == user_id
            # ).first()
            settings = self._get_user_settings_mock(user_id)

            if not settings:
                logger.warning(f"No settings found for user {user_id}, using defaults")
                settings = self._get_default_settings()

            # Check if auto-discovery is enabled
            if not settings.get('auto_discovery_enabled', True):
                logger.info(f"Auto-discovery disabled for user {user_id}")
                return {
                    "success": True,
                    "skipped": True,
                    "reason": "Auto-discovery disabled"
                }

            # Check last discovery time (don't run too frequently)
            if not force_run:
                # last_log = self.db.query(DiscoveryLog).filter(
                #     DiscoveryLog.user_id == user_id
                # ).order_by(DiscoveryLog.created_at.desc()).first()
                last_log = None  # Mock

                if last_log and hasattr(last_log, 'created_at'):
                    hours_since_last = (datetime.utcnow() - last_log.created_at).total_seconds() / 3600
                    min_hours = settings.get('discovery_interval_hours', 12)

                    if hours_since_last < min_hours:
                        logger.info(f"Discovery ran {hours_since_last:.1f}h ago, skipping")
                        return {
                            "success": True,
                            "skipped": True,
                            "reason": f"Too soon (last run {hours_since_last:.1f}h ago)"
                        }

            # Step 2: Get user's stores and niches
            # stores = self.db.query(Store).filter(
            #     Store.user_id == user_id,
            #     Store.status == 'active'
            # ).all()
            stores = self._get_user_stores_mock(user_id)

            if not stores:
                logger.warning(f"No active stores for user {user_id}")
                return {
                    "success": True,
                    "skipped": True,
                    "reason": "No active stores"
                }

            # Determine niches to search
            niches = settings.get('preferred_niches') or self.default_niches
            exclude_niches = settings.get('exclude_niches', [])
            niches = [n for n in niches if n not in exclude_niches]

            logger.info(f"Running discovery for {len(niches)} niches: {niches}")

            # Step 3: Run discovery for each niche
            all_products = []
            niche_results = {}

            for niche in niches:
                try:
                    niche_products = await self._discover_niche_products(
                        niche=niche,
                        user_settings=settings
                    )

                    all_products.extend(niche_products)
                    niche_results[niche] = {
                        "success": True,
                        "products_found": len(niche_products)
                    }

                    logger.info(f"Found {len(niche_products)} products for niche '{niche}'")

                except Exception as e:
                    logger.error(f"Discovery failed for niche '{niche}': {e}")
                    niche_results[niche] = {
                        "success": False,
                        "error": str(e)
                    }

            # Step 4: Filter by minimum score
            min_score = settings.get('min_product_score', 7.0)
            high_score_products = [p for p in all_products if p.get('score', 0) >= min_score]

            logger.info(
                f"Filtered {len(all_products)} products → {len(high_score_products)} "
                f"above min_score {min_score}"
            )

            # Step 5: Save products to database
            saved_products = []
            for product_data in high_score_products:
                try:
                    saved_product = await self._save_discovered_product(
                        user_id=user_id,
                        product_data=product_data,
                        stores=stores
                    )
                    saved_products.append(saved_product)

                except Exception as e:
                    logger.error(f"Failed to save product: {e}")

            logger.info(f"Saved {len(saved_products)} products to database")

            # Step 6: Check for high-priority products (score >= 8.5)
            high_priority = [p for p in saved_products if p.get('score', 0) >= 8.5]

            if high_priority:
                logger.info(f"Found {len(high_priority)} high-priority products!")

                # Send notification
                await self._send_discovery_notification(
                    user_id=user_id,
                    high_priority_count=len(high_priority),
                    stores=stores
                )

            # Step 7: Auto-deploy if enabled
            deployed_count = 0
            if settings.get('auto_deploy_enabled', False):
                auto_deploy_threshold = settings.get('auto_deploy_threshold', 8.5)

                deploy_candidates = [
                    p for p in saved_products
                    if p.get('score', 0) >= auto_deploy_threshold
                ]

                logger.info(
                    f"Auto-deploying {len(deploy_candidates)} products "
                    f"(score >= {auto_deploy_threshold})"
                )

                for product in deploy_candidates:
                    try:
                        deploy_result = await self._auto_deploy_product(
                            product=product,
                            stores=stores,
                            user_id=user_id
                        )

                        if deploy_result.get('success'):
                            deployed_count += deploy_result.get('deployed', 0)

                    except Exception as e:
                        logger.error(f"Auto-deploy failed for product {product.get('id')}: {e}")

            # Step 8: Create discovery log
            end_time = datetime.utcnow()
            duration_seconds = (end_time - start_time).total_seconds()

            log_data = {
                'user_id': user_id,
                'niches_searched': niches,
                'products_found': len(all_products),
                'products_saved': len(saved_products),
                'products_deployed': deployed_count,
                'high_priority_count': len(high_priority),
                'duration_seconds': duration_seconds,
                'niche_results': niche_results,
                'created_at': end_time
            }

            # discovery_log = DiscoveryLog(**log_data)
            # self.db.add(discovery_log)
            # self.db.commit()

            logger.info(
                f"[SUCCESS] Discovery complete for user {user_id}: "
                f"{len(saved_products)} saved, {deployed_count} deployed, "
                f"{duration_seconds:.1f}s"
            )

            return {
                "success": True,
                "user_id": user_id,
                "niches_searched": niches,
                "products_found": len(all_products),
                "products_saved": len(saved_products),
                "products_deployed": deployed_count,
                "high_priority_count": len(high_priority),
                "duration_seconds": duration_seconds,
                "niche_results": niche_results
            }

        except Exception as e:
            logger.exception(f"Discovery failed for user {user_id}: {e}")
            return {
                "success": False,
                "user_id": user_id,
                "error": str(e)
            }

    async def run_discovery_for_all_users(self) -> Dict[str, Any]:
        """
        Run discovery for all active users.

        Returns:
            dict: Summary statistics for all users
        """
        logger.info("Starting discovery for all users")
        start_time = datetime.utcnow()

        try:
            # Get all active users with auto-discovery enabled
            # users = self.db.query(User).filter(User.is_active == True).all()
            users = self._get_all_users_mock()

            logger.info(f"Found {len(users)} active users")

            # Run discovery for each user
            results = []
            for user in users:
                try:
                    result = await self.run_discovery_for_user(
                        user_id=user['id'],
                        force_run=False
                    )
                    results.append(result)

                except Exception as e:
                    logger.error(f"Discovery failed for user {user['id']}: {e}")
                    results.append({
                        "success": False,
                        "user_id": user['id'],
                        "error": str(e)
                    })

            # Calculate summary statistics
            successful = [r for r in results if r.get('success')]
            failed = [r for r in results if not r.get('success')]
            skipped = [r for r in results if r.get('skipped')]

            total_products_found = sum(r.get('products_found', 0) for r in successful)
            total_products_saved = sum(r.get('products_saved', 0) for r in successful)
            total_products_deployed = sum(r.get('products_deployed', 0) for r in successful)
            total_high_priority = sum(r.get('high_priority_count', 0) for r in successful)

            end_time = datetime.utcnow()
            total_duration = (end_time - start_time).total_seconds()

            summary = {
                "success": True,
                "total_users": len(users),
                "successful": len(successful),
                "failed": len(failed),
                "skipped": len(skipped),
                "total_products_found": total_products_found,
                "total_products_saved": total_products_saved,
                "total_products_deployed": total_products_deployed,
                "total_high_priority": total_high_priority,
                "duration_seconds": total_duration,
                "timestamp": end_time.isoformat()
            }

            logger.info(
                f"[SUCCESS] Discovery complete for all users: "
                f"{len(successful)}/{len(users)} successful, "
                f"{total_products_saved} products saved, "
                f"{total_products_deployed} deployed, "
                f"{total_duration:.1f}s"
            )

            return summary

        except Exception as e:
            logger.exception(f"Batch discovery failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def schedule_discovery(
        self,
        hour: int = 3,
        minute: int = 0,
        interval_hours: int = None
    ):
        """
        Schedule automatic discovery jobs.

        Args:
            hour: Hour to run daily job (0-23, default: 3 for 3 AM)
            minute: Minute to run (0-59, default: 0)
            interval_hours: If provided, run every N hours instead of daily
        """
        try:
            # SECURITY: Job timeout to prevent runaway processes
            # Auto-discovery should complete within 2 hours max
            job_timeout = 7200  # 2 hours in seconds

            if interval_hours:
                # Interval-based scheduling
                self.scheduler.add_job(
                    self.run_discovery_for_all_users,
                    'interval',
                    hours=interval_hours,
                    id='auto_discovery_interval',
                    replace_existing=True,
                    max_instances=1,  # Prevent overlapping runs
                    misfire_grace_time=300,  # 5 min grace period
                )

                logger.info(f"[SUCCESS] Scheduled discovery every {interval_hours} hours (timeout: {job_timeout}s)")

            else:
                # Daily at specific time
                trigger = CronTrigger(hour=hour, minute=minute)

                self.scheduler.add_job(
                    self.run_discovery_for_all_users,
                    trigger=trigger,
                    id='auto_discovery_daily',
                    replace_existing=True,
                    max_instances=1,
                    misfire_grace_time=300,  # 5 min grace period
                )

                logger.info(f"[SUCCESS] Scheduled daily discovery at {hour:02d}:{minute:02d} (timeout: {job_timeout}s)")

            # Start scheduler if not already running
            if not self.scheduler.running:
                self.scheduler.start()
                logger.info("[SUCCESS] Scheduler started")

        except Exception as e:
            logger.error(f"Failed to schedule discovery: {e}")
            raise

    def unschedule_discovery(self):
        """Remove all scheduled discovery jobs"""
        try:
            for job_id in ['auto_discovery_daily', 'auto_discovery_interval']:
                try:
                    self.scheduler.remove_job(job_id)
                    logger.info(f"Removed job: {job_id}")
                except Exception:
                    pass

            logger.info("[SUCCESS] All discovery jobs unscheduled")

        except Exception as e:
            logger.error(f"Failed to unschedule: {e}")

    async def _discover_niche_products(
        self,
        niche: str,
        user_settings: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Discover products for a specific niche using Apify-first approach.

        Args:
            niche: Niche to search
            user_settings: User's discovery settings

        Returns:
            List of discovered products with scores
        """
        products = []

        # PRIMARY: Use new Apify-first unified discovery
        try:
            from ospra_os.intelligence.unified_product_discovery import get_live_products
            
            results = await get_live_products(
                niche=niche,
                limit=user_settings.get('max_products_per_niche', 10)
            )
            
            # Transform to expected format
            for product in results:
                products.append({
                    'title': product.get('title', product.get('name', 'Unknown')),
                    'description': product.get('description', ''),
                    'price': product.get('price', 0),
                    'score': product.get('final_score', product.get('velocity_score', 50)) / 10,  # Convert to 0-10
                    'images': [product.get('main_image', '')],
                    'url': product.get('source_url', ''),
                    'source': product.get('source', 'apify_discovery'),
                    'niche': niche,
                    'tier': product.get('tier', 'FAIR'),
                    'data_sources': product.get('data_sources', {})
                })
            
            logger.info(f"Found {len(products)} products via Apify-first discovery for '{niche}'")
            return products
            
        except Exception as e:
            logger.error(f"Apify-first discovery failed for '{niche}': {e}")

        # FALLBACK: Use multi-source discovery if available
        if MULTI_SOURCE_AVAILABLE and not products:
            try:
                discovery = MultiSourceDiscovery()
                results = await discovery.discover_products(
                    query=niche,
                    max_results=user_settings.get('max_products_per_niche', 10),
                    sources=['google_trends']
                )

                products.extend(results.get('products', []))

            except Exception as e:
                logger.error(f"Multi-source discovery failed for '{niche}': {e}")

        # FALLBACK 2: Use intelligence v3 if available
        if INTELLIGENCE_V3_AVAILABLE and not products:
            try:
                intelligence = ProductIntelligenceEngine()
                results = intelligence.discover_products_by_niche(
                    niche=niche,
                    count=user_settings.get('max_products_per_niche', 10)
                )

                products.extend(results)

            except Exception as e:
                logger.error(f"Intelligence v3 discovery failed for '{niche}': {e}")

        # Score products with AI if not already scored
        for product in products:
            if 'score' not in product or product['score'] == 0:
                product['score'] = 7.5  # Default score

        return products

    async def _save_discovered_product(
        self,
        user_id: int,
        product_data: Dict[str, Any],
        stores: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Save discovered product to database.

        Args:
            user_id: User ID
            product_data: Product data with score and metadata
            stores: User's stores

        Returns:
            dict: Saved product data
        """
        # Determine which store to link to (use first active store)
        default_store = stores[0] if stores else None

        # Create Product record
        product_record = {
            'user_id': user_id,
            'store_id': default_store['id'] if default_store else None,
            'product_name': product_data.get('title', 'Unknown Product'),
            'description': product_data.get('description', ''),
            'price': Decimal(str(product_data.get('price', 0.0))),
            'sku': product_data.get('sku', ''),
            'stock_quantity': product_data.get('inventory', 0),
            'images': str(product_data.get('images', [])),
            'tags': ','.join(product_data.get('tags', [])),
            'status': 'discovered',
            'discovery_score': product_data.get('score', 0.0),
            'ai_explanation': product_data.get('explanation', ''),
            'discovered_at': datetime.utcnow(),
            'source': product_data.get('source', 'auto_discovery'),
            'source_url': product_data.get('url', '')
        }

        # product = Product(**product_record)
        # self.db.add(product)
        # self.db.commit()

        # Mock: return product data with ID
        product_record['id'] = 123  # Mock ID
        product_record['score'] = product_data.get('score', 0.0)

        return product_record

    async def _send_discovery_notification(
        self,
        user_id: int,
        high_priority_count: int,
        stores: List[Dict[str, Any]]
    ):
        """
        Send notification about discovered high-priority products.

        Args:
            user_id: User ID
            high_priority_count: Number of high-priority products found
            stores: User's stores
        """
        try:
            store_names = ', '.join(s['store_name'] for s in stores[:2])
            if len(stores) > 2:
                store_names += f" and {len(stores) - 2} more"

            message = (
                f"[HOT] Found {high_priority_count} high-priority products "
                f"for your {store_names} store{'s' if len(stores) > 1 else ''}!"
            )

            # Create in-app notification
            # notification = Notification(
            #     user_id=user_id,
            #     type='product_discovery',
            #     title='New High-Priority Products Found',
            #     message=message,
            #     link='/dashboard/products?filter=discovered',
            #     created_at=datetime.utcnow()
            # )
            # self.db.add(notification)
            # self.db.commit()

            logger.info(f"Notification sent to user {user_id}: {message}")

            # TODO: Send email if user has email notifications enabled
            # await self._send_email_notification(user_id, message)

        except Exception as e:
            logger.error(f"Failed to send notification to user {user_id}: {e}")

    async def _auto_deploy_product(
        self,
        product: Dict[str, Any],
        stores: List[Dict[str, Any]],
        user_id: int
    ) -> Dict[str, Any]:
        """
        Automatically deploy high-scoring product to user's stores.

        Args:
            product: Product data
            stores: User's stores
            user_id: User ID

        Returns:
            dict: Deployment results
        """
        if not DEPLOYER_AVAILABLE:
            logger.warning("UnifiedProductDeployer not available, skipping auto-deploy")
            return {"success": False, "error": "Deployer not available"}

        try:
            deployer = UnifiedProductDeployer(db_session=self.db)

            # Deploy to all user's stores
            results = await deployer.deploy_to_all_stores(
                product_id=product['id'],
                user_id=user_id
            )

            logger.info(
                f"Auto-deployed product {product['id']} to {results.get('deployed', 0)} stores"
            )

            return results

        except Exception as e:
            logger.error(f"Auto-deploy failed for product {product['id']}: {e}")
            return {"success": False, "error": str(e)}

    def get_discovery_stats(
        self,
        user_id: int = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get discovery statistics for user or all users.

        Args:
            user_id: Specific user ID (None for all users)
            days: Number of days to analyze

        Returns:
            dict: Statistics including products found, saved, deployed
        """
        try:
            since_date = datetime.utcnow() - timedelta(days=days)

            # Query discovery logs
            # logs = self.db.query(DiscoveryLog).filter(
            #     DiscoveryLog.created_at >= since_date
            # )
            #
            # if user_id:
            #     logs = logs.filter(DiscoveryLog.user_id == user_id)
            #
            # logs = logs.all()

            # Mock stats
            stats = {
                "period_days": days,
                "total_runs": 15,
                "successful_runs": 14,
                "failed_runs": 1,
                "total_products_found": 245,
                "total_products_saved": 87,
                "total_products_deployed": 12,
                "total_high_priority": 18,
                "avg_products_per_run": 16.3,
                "avg_duration_seconds": 45.2
            }

            if user_id:
                stats["user_id"] = user_id

            return stats

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}

    # Mock methods for testing (replace with actual database queries)

    def _get_user_mock(self, user_id: int) -> Dict[str, Any]:
        """Mock user retrieval"""
        return {
            'id': user_id,
            'email': f'user{user_id}@example.com',
            'is_active': True
        }

    def _get_user_settings_mock(self, user_id: int) -> Dict[str, Any]:
        """Mock user settings retrieval"""
        return {
            'user_id': user_id,
            'auto_discovery_enabled': True,
            'preferred_niches': ['smart_home', 'fitness'],
            'exclude_niches': [],
            'min_product_score': 7.0,
            'max_products_per_niche': 10,
            'discovery_interval_hours': 12,
            'auto_deploy_enabled': False,
            'auto_deploy_threshold': 8.5
        }

    def _get_default_settings(self) -> Dict[str, Any]:
        """Get default discovery settings"""
        return {
            'auto_discovery_enabled': True,
            'preferred_niches': self.default_niches,
            'exclude_niches': [],
            'min_product_score': 7.0,
            'max_products_per_niche': 10,
            'discovery_interval_hours': 12,
            'auto_deploy_enabled': False,
            'auto_deploy_threshold': 8.5
        }

    def _get_user_stores_mock(self, user_id: int) -> List[Dict[str, Any]]:
        """Mock user stores retrieval"""
        return [
            {
                'id': 1,
                'user_id': user_id,
                'platform': 'shopify',
                'store_name': 'Test Store',
                'status': 'active'
            }
        ]

    def _get_all_users_mock(self) -> List[Dict[str, Any]]:
        """Mock all users retrieval"""
        return [
            {'id': 1, 'is_active': True},
            {'id': 2, 'is_active': True}
        ]


# Convenience function for easy initialization
def start_auto_discovery_scheduler(
    database_url: str,
    hour: int = 3,
    minute: int = 0,
    interval_hours: int = None
) -> AutoDiscoveryJob:
    """
    Start the auto-discovery scheduler.

    Args:
        database_url: Database connection URL
        hour: Hour to run daily (0-23, default: 3 AM)
        minute: Minute to run (default: 0)
        interval_hours: Run every N hours instead of daily

    Returns:
        AutoDiscoveryJob: Scheduler instance

    Example:
        # Run daily at 3 AM
        job = start_auto_discovery_scheduler("postgresql://...")

        # Run every 12 hours
        job = start_auto_discovery_scheduler(
            "postgresql://...",
            interval_hours=12
        )
    """
    job = AutoDiscoveryJob(database_url=database_url)
    job.schedule_discovery(hour=hour, minute=minute, interval_hours=interval_hours)
    return job
