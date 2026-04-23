"""
Auto-Deployment Service

Automatically deploys high-scoring products that meet criteria.
Runs on a schedule and includes safety features to prevent over-deployment.

Features:
- Criteria-based filtering (score, margin, saturation, niche)
- Daily deployment limits
- AI-powered deployment with full pipeline
- Admin notifications (email, Slack, webhook)
- Draft-first deployment for safety
- Deployment history tracking
- Cost tracking and budgets

Author: OspraOS
Date: December 2025
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import json

from ospra_os.services.product_deployer import ProductDeployer
from ospra_os.intelligence.product_discovery import ProductDiscoveryEngine as UnifiedProductDiscovery

logger = logging.getLogger(__name__)

Base = declarative_base()


# ============================================================================
# DATABASE MODELS
# ============================================================================

class AutoDeployment(Base):
    """Track auto-deployments"""
    __tablename__ = "auto_deployments"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String, index=True)
    product_name = Column(String)
    niche = Column(String, index=True)
    score = Column(Float)
    profit_margin = Column(Float)

    shopify_product_id = Column(String, nullable=True)
    shopify_url = Column(String, nullable=True)

    success = Column(Boolean, default=False)
    error = Column(Text, nullable=True)

    ai_cost = Column(Float, default=0.0)
    processing_time = Column(Float, default=0.0)

    deployed_at = Column(DateTime, default=datetime.utcnow)
    criteria_snapshot = Column(Text)  # JSON snapshot of criteria used


class AutoDeploySettings(Base):
    """Auto-deploy settings (singleton)"""
    __tablename__ = "auto_deploy_settings"

    id = Column(Integer, primary_key=True)
    enabled = Column(Boolean, default=False)
    criteria_json = Column(Text)
    last_run = Column(DateTime, nullable=True)
    total_deployed = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================================
# AUTO DEPLOYER SERVICE
# ============================================================================

class AutoDeployer:
    """
    Automated product deployment service.

    Monitors product discovery feed and auto-deploys products that meet
    criteria. Includes safety features and admin controls.
    """

    def __init__(self, db_url: str = "sqlite:///./data/auto_deploy.db"):
        """Initialize auto-deployer"""
        self.db_url = db_url
        self._setup_database()

        # Initialize services
        self.deployer = ProductDeployer()
        self.discovery = UnifiedProductDiscovery()

        # Load settings from database
        self.settings = self._load_settings()

        logger.info("[SUCCESS] AutoDeployer initialized")

    def _setup_database(self):
        """Setup SQLite database for tracking"""
        engine = create_engine(self.db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        logger.info(f"[SUCCESS] Auto-deploy database initialized: {self.db_url}")

    def _load_settings(self) -> Dict:
        """Load settings from database or create defaults"""
        db = self.SessionLocal()
        try:
            settings = db.query(AutoDeploySettings).first()
            if not settings:
                # Create default settings
                default_criteria = {
                    "min_score": 80.0,           # Minimum product score (0-100)
                    "min_profit_margin": 0.35,   # 35% minimum margin
                    "max_saturation": "medium",  # Max market saturation level
                    "allowed_niches": ["smart_home", "fitness", "tech_gadgets", "kitchen"],
                    "max_per_day": 5,            # Don't flood the store
                    "max_per_hour": 2,           # Rate limiting
                    "max_daily_cost": 1.0,       # Max $1/day in AI costs
                    "require_multiple_sources": True,  # Must be validated by multiple sources
                    "min_trend_velocity": 70.0,  # Google Trends velocity
                    "auto_publish": False,       # Always save as draft for safety
                }

                settings = AutoDeploySettings(
                    enabled=False,
                    criteria_json=json.dumps(default_criteria),
                    total_deployed=0,
                    total_cost=0.0
                )
                db.add(settings)
                db.commit()
                db.refresh(settings)
                logger.info("[SUCCESS] Created default auto-deploy settings")

            return {
                "enabled": settings.enabled,
                "criteria": json.loads(settings.criteria_json),
                "last_run": settings.last_run,
                "total_deployed": settings.total_deployed,
                "total_cost": settings.total_cost
            }
        finally:
            db.close()

    def _save_settings(self):
        """Save current settings to database"""
        db = self.SessionLocal()
        try:
            settings = db.query(AutoDeploySettings).first()
            if settings:
                settings.enabled = self.settings["enabled"]
                settings.criteria_json = json.dumps(self.settings["criteria"])
                settings.last_run = self.settings.get("last_run")
                settings.total_deployed = self.settings.get("total_deployed", 0)
                settings.total_cost = self.settings.get("total_cost", 0.0)
                settings.updated_at = datetime.utcnow()
                db.commit()
                logger.info("[SUCCESS] Auto-deploy settings saved")
        finally:
            db.close()

    async def check_and_deploy(self) -> Dict:
        """
        Main scheduled task. Checks for high-scoring products and auto-deploys.

        Returns:
            Dict with deployment results and statistics
        """
        if not self.settings["enabled"]:
            logger.info("⏭  Auto-deploy is disabled, skipping")
            return {
                "success": False,
                "reason": "Auto-deploy is disabled",
                "deployed": 0
            }

        logger.info("=" * 70)
        logger.info("[AI] AUTO-DEPLOY: Starting scheduled check...")
        logger.info("=" * 70)

        try:
            # Update last run time
            self.settings["last_run"] = datetime.utcnow()
            self._save_settings()

            # Check daily limits
            if not await self._check_daily_limits():
                logger.info("⏭  Daily limits reached, skipping")
                return {
                    "success": False,
                    "reason": "Daily limits reached",
                    "deployed": 0
                }

            # Get deployment candidates
            logger.info("[SEARCH] Finding deployment candidates...")
            candidates = await self.get_deployment_candidates()

            if not candidates:
                logger.info(" No products meet deployment criteria")
                return {
                    "success": True,
                    "reason": "No candidates found",
                    "deployed": 0
                }

            logger.info(f"[SUCCESS] Found {len(candidates)} deployment candidates")

            # Filter by hourly and daily limits
            criteria = self.settings["criteria"]
            max_to_deploy = min(
                criteria.get("max_per_hour", 2),
                await self._get_remaining_daily_quota()
            )

            to_deploy = candidates[:max_to_deploy]
            logger.info(f"[PACKAGE] Deploying {len(to_deploy)} products (limit: {max_to_deploy})")

            # Deploy each product
            results = []
            successful = 0
            failed = 0
            total_cost = 0.0

            for i, product in enumerate(to_deploy, 1):
                logger.info(f"\n{'='*70}")
                logger.info(f"[START] Deploying {i}/{len(to_deploy)}: {product['name'][:50]}")
                logger.info(f"{'='*70}")

                try:
                    result = await self._deploy_product(product)
                    results.append(result)

                    if result["success"]:
                        successful += 1
                        total_cost += result.get("total_cost", 0.0)

                        # Track deployment
                        await self._track_deployment(product, result)

                        # Notify admin
                        await self._notify_admin(product, result)

                        logger.info(f"[SUCCESS] Deployed successfully: {result.get('shopify_url')}")
                    else:
                        failed += 1
                        logger.error(f"[ERROR] Deployment failed: {result.get('error')}")

                    # Rate limiting pause between deployments
                    if i < len(to_deploy):
                        logger.info("[PAUSE]  Pausing 30s between deployments...")
                        await asyncio.sleep(30)

                except Exception as e:
                    failed += 1
                    logger.error(f"[ERROR] Deployment error: {e}")
                    results.append({
                        "success": False,
                        "product_name": product.get("name"),
                        "error": str(e)
                    })

            # Update totals
            self.settings["total_deployed"] = self.settings.get("total_deployed", 0) + successful
            self.settings["total_cost"] = self.settings.get("total_cost", 0.0) + total_cost
            self._save_settings()

            logger.info("\n" + "=" * 70)
            logger.info(f"[TARGET] AUTO-DEPLOY COMPLETE")
            logger.info("=" * 70)
            logger.info(f"[SUCCESS] Successful: {successful}")
            logger.info(f"[ERROR] Failed: {failed}")
            logger.info(f"[PRICE] Total cost: ${total_cost:.2f}")
            logger.info(f"[STATS] All-time deployed: {self.settings['total_deployed']}")
            logger.info("=" * 70)

            return {
                "success": True,
                "deployed": successful,
                "failed": failed,
                "total_cost": total_cost,
                "results": results
            }

        except Exception as e:
            logger.error(f"[ERROR] Auto-deploy check failed: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "deployed": 0
            }

    async def get_deployment_candidates(self) -> List[Dict]:
        """
        Get products that meet auto-deploy criteria.

        Returns:
            List of products ready for deployment
        """
        criteria = self.settings["criteria"]
        candidates = []

        # Discover products from all niches
        for niche in criteria["allowed_niches"]:
            try:
                logger.info(f"[SEARCH] Discovering products in {niche}...")

                # Use unified discovery to find trending products
                products = await self.discovery.discover_products(
                    niche=niche,
                    max_products=10,  # Get top 10 per niche
                    min_score=criteria["min_score"]
                )

                # Filter by criteria
                for product in products:
                    if await self._meets_criteria(product):
                        # Check if already deployed
                        if not await self._is_already_deployed(product):
                            candidates.append(product)
                            logger.info(f"[SUCCESS] Candidate: {product.get('name', 'Unknown')[:50]} (score: {product.get('score', 0)})")

            except Exception as e:
                logger.error(f"[ERROR] Discovery failed for {niche}: {e}")
                continue

        # Sort by score (highest first)
        candidates.sort(key=lambda p: p.get("score", 0), reverse=True)

        logger.info(f"[SUCCESS] Found {len(candidates)} total candidates across all niches")
        return candidates

    async def _meets_criteria(self, product: Dict) -> bool:
        """Check if product meets all deployment criteria"""
        criteria = self.settings["criteria"]

        # Check score
        score = product.get("score", 0)
        if score < criteria["min_score"]:
            return False

        # Check profit margin
        cost = product.get("cost_price", 0) or product.get("price", 0)
        retail = product.get("retail_price", 0)
        if cost > 0 and retail > 0:
            margin = (retail - cost) / retail
            if margin < criteria["min_profit_margin"]:
                return False

        # Check saturation level
        saturation = product.get("saturation_level", "unknown")
        max_saturation = criteria["max_saturation"]
        saturation_levels = ["low", "medium", "high", "saturated"]
        if saturation_levels.index(saturation) > saturation_levels.index(max_saturation):
            return False

        # Check multiple sources requirement
        if criteria.get("require_multiple_sources", True):
            source_count = product.get("source_count", 0)
            if source_count < 2:
                return False

        # Check trend velocity
        trend_velocity = product.get("trend_velocity", 0)
        if trend_velocity < criteria.get("min_trend_velocity", 70.0):
            return False

        return True

    async def _deploy_product(self, product: Dict) -> Dict:
        """Deploy a single product with full AI pipeline"""
        criteria = self.settings["criteria"]

        # Prepare product data for deployer
        aliexpress_product = {
            "title": product.get("name", ""),
            "description": product.get("description", ""),
            "features": product.get("features", []),
            "category": product.get("category", ""),
            "price": product.get("cost_price", 0) or product.get("price", 0),
            "images": product.get("images", [])
        }

        # Deployment options
        options = {
            "enhance_images": True,
            "generate_content": True,
            "generate_seo": True,
            "generate_pricing": True,
            "publish_immediately": criteria.get("auto_publish", False),  # Default: draft
            "add_branding": True,
            "target_margin": criteria.get("min_profit_margin", 0.35),
            "max_images": 3  # Limit to save costs
        }

        # Deploy
        result = await self.deployer.deploy_product(
            aliexpress_product=aliexpress_product,
            niche=product.get("niche", "general"),
            shopify_store_id=None,  # Use default store
            options=options
        )

        return result

    async def _is_already_deployed(self, product: Dict) -> bool:
        """Check if product has already been auto-deployed"""
        db = self.SessionLocal()
        try:
            product_id = product.get("id") or product.get("product_id")
            if not product_id:
                return False

            existing = db.query(AutoDeployment).filter(
                AutoDeployment.product_id == str(product_id)
            ).first()

            return existing is not None
        finally:
            db.close()

    async def _track_deployment(self, product: Dict, result: Dict):
        """Track deployment in database"""
        db = self.SessionLocal()
        try:
            deployment = AutoDeployment(
                product_id=product.get("id") or product.get("product_id", "unknown"),
                product_name=product.get("name", "Unknown"),
                niche=product.get("niche", "general"),
                score=product.get("score", 0.0),
                profit_margin=result.get("pricing", {}).get("profit_margin", 0.0),
                shopify_product_id=result.get("shopify_product_id"),
                shopify_url=result.get("shopify_url"),
                success=result.get("success", False),
                error=result.get("error"),
                ai_cost=result.get("total_cost", 0.0),
                processing_time=result.get("processing_time_seconds", 0.0),
                criteria_snapshot=json.dumps(self.settings["criteria"])
            )
            db.add(deployment)
            db.commit()
            logger.info("[SUCCESS] Deployment tracked in database")
        finally:
            db.close()

    async def _notify_admin(self, product: Dict, result: Dict):
        """Send notification to admin about auto-deployment"""
        try:
            # Email notification (if configured)
            from ospra_os.notifications.email_notifier import EmailNotifier
            notifier = EmailNotifier()

            if result.get("success"):
                subject = f"[SUCCESS] Auto-Deployed: {product.get('name', 'Product')[:50]}"
                message = f"""
                Auto-deployment successful!

                Product: {product.get('name')}
                Niche: {product.get('niche')}
                Score: {product.get('score', 0)}/100

                Shopify URL: {result.get('shopify_url')}
                Admin URL: {result.get('admin_url')}

                Price: ${result.get('pricing', {}).get('retail_price', 0):.2f}
                Margin: {result.get('pricing', {}).get('profit_margin', 0):.1f}%

                AI Cost: ${result.get('total_cost', 0):.2f}
                Processing Time: {result.get('processing_time_seconds', 0):.1f}s

                Status: {'Published' if result.get('published') else 'Draft'}
                """

                await notifier.send_notification(
                    subject=subject,
                    message=message,
                    priority="medium"
                )
            else:
                subject = f"[ERROR] Auto-Deploy Failed: {product.get('name', 'Product')[:50]}"
                message = f"""
                Auto-deployment failed.

                Product: {product.get('name')}
                Niche: {product.get('niche')}
                Error: {result.get('error')}
                """

                await notifier.send_notification(
                    subject=subject,
                    message=message,
                    priority="high"
                )

        except Exception as e:
            logger.error(f"[WARNING]  Failed to send notification: {e}")

    async def _check_daily_limits(self) -> bool:
        """Check if daily deployment limits have been reached"""
        db = self.SessionLocal()
        try:
            # Count deployments in last 24 hours
            since = datetime.utcnow() - timedelta(hours=24)
            count = db.query(AutoDeployment).filter(
                AutoDeployment.deployed_at >= since,
                AutoDeployment.success == True
            ).count()

            max_per_day = self.settings["criteria"].get("max_per_day", 5)

            if count >= max_per_day:
                logger.warning(f"[WARNING]  Daily limit reached: {count}/{max_per_day}")
                return False

            # Check daily cost limit
            total_cost = db.query(AutoDeployment).filter(
                AutoDeployment.deployed_at >= since
            ).with_entities(AutoDeployment.ai_cost).all()

            daily_cost = sum(cost[0] or 0.0 for cost in total_cost)
            max_daily_cost = self.settings["criteria"].get("max_daily_cost", 1.0)

            if daily_cost >= max_daily_cost:
                logger.warning(f"[WARNING]  Daily cost limit reached: ${daily_cost:.2f}/${max_daily_cost:.2f}")
                return False

            logger.info(f"[SUCCESS] Daily limits OK: {count}/{max_per_day} deployments, ${daily_cost:.2f}/${max_daily_cost:.2f} spent")
            return True

        finally:
            db.close()

    async def _get_remaining_daily_quota(self) -> int:
        """Get remaining deployment quota for today"""
        db = self.SessionLocal()
        try:
            since = datetime.utcnow() - timedelta(hours=24)
            count = db.query(AutoDeployment).filter(
                AutoDeployment.deployed_at >= since,
                AutoDeployment.success == True
            ).count()

            max_per_day = self.settings["criteria"].get("max_per_day", 5)
            return max(0, max_per_day - count)
        finally:
            db.close()

    def enable(self):
        """Enable auto-deployment"""
        self.settings["enabled"] = True
        self._save_settings()
        logger.info("[SUCCESS] Auto-deployment ENABLED")

    def disable(self):
        """Disable auto-deployment"""
        self.settings["enabled"] = False
        self._save_settings()
        logger.info("[PAUSE]  Auto-deployment DISABLED")

    def update_criteria(self, new_criteria: Dict):
        """Update deployment criteria"""
        self.settings["criteria"].update(new_criteria)
        self._save_settings()
        logger.info(f"[SUCCESS] Criteria updated: {new_criteria}")

    def get_status(self) -> Dict:
        """Get current auto-deploy status"""
        return {
            "enabled": self.settings["enabled"],
            "criteria": self.settings["criteria"],
            "last_run": self.settings.get("last_run"),
            "total_deployed": self.settings.get("total_deployed", 0),
            "total_cost": self.settings.get("total_cost", 0.0)
        }

    def get_history(self, limit: int = 50) -> List[Dict]:
        """Get deployment history"""
        db = self.SessionLocal()
        try:
            deployments = db.query(AutoDeployment).order_by(
                AutoDeployment.deployed_at.desc()
            ).limit(limit).all()

            return [{
                "id": d.id,
                "product_name": d.product_name,
                "niche": d.niche,
                "score": d.score,
                "shopify_url": d.shopify_url,
                "success": d.success,
                "error": d.error,
                "ai_cost": d.ai_cost,
                "deployed_at": d.deployed_at.isoformat() if d.deployed_at else None
            } for d in deployments]
        finally:
            db.close()
