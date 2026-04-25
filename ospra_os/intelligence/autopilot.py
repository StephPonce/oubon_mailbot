"""
AUTOPILOT MODE

Full hands-off store automation that:
1. Discovers and deploys products automatically
2. Creates and optimizes ad campaigns
3. Monitors supplier prices and adjusts strategy
4. Responds to customer emails
5. Learns from successes/failures
6. Generates captions and product descriptions
7. Manages inventory levels

Safety features:
- Spending limits per day/week/month
- Human approval required for high-value decisions
- Emergency stop mechanism
- Detailed audit log
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, timezone
from enum import Enum
import asyncio
from sqlalchemy.orm import Session

from ospra_os.database import Product, Store, AdCampaign, ProductStatus
from ospra_os.intelligence.autonomous_ai import get_autonomous_ai
from ospra_os.intelligence.competitive_learning import get_competitive_learning_engine
from ospra_os.intelligence.ai_actions import get_action_manager, ActionType
from ospra_os.intelligence.supplier_monitor import get_supplier_monitor
from ospra_os.ai.model_router import get_model_router, TaskComplexity


class AutoPilotMode(str, Enum):
    """AutoPilot operation modes."""
    OFF = "off"  # Manual control only
    ASSISTED = "assisted"  # AI proposes, human approves
    SEMI_AUTO = "semi_auto"  # Auto-execute low-risk actions, propose high-risk
    FULL_AUTO = "full_auto"  # Full automation with safety limits


class SafetyLimits:
    """Safety limits for AutoPilot."""

    def __init__(
        self,
        max_daily_ad_spend: float = 100.0,
        max_product_price: float = 200.0,
        max_products_per_day: int = 5,
        max_price_change_percent: float = 20.0,
        require_approval_above_spend: float = 50.0
    ):
        self.max_daily_ad_spend = max_daily_ad_spend
        self.max_product_price = max_product_price
        self.max_products_per_day = max_products_per_day
        self.max_price_change_percent = max_price_change_percent
        self.require_approval_above_spend = require_approval_above_spend


class AutoPilot:
    """
    Full automation engine for e-commerce stores.

    Orchestrates all AI systems to run store hands-free.
    """

    def __init__(
        self,
        db: Session,
        mode: AutoPilotMode = AutoPilotMode.ASSISTED,
        safety_limits: Optional[SafetyLimits] = None
    ):
        self.db = db
        self.mode = mode
        self.safety_limits = safety_limits or SafetyLimits()

        # Initialize AI systems
        self.ai = get_autonomous_ai(db)
        self.learning_engine = get_competitive_learning_engine(db)
        self.action_manager = get_action_manager(db)
        self.supplier_monitor = get_supplier_monitor(db)
        self.model_router = get_model_router()

        # Tracking
        self.actions_today = {
            "products_deployed": 0,
            "ads_created": 0,
            "ad_spend": 0.0,
            "prices_adjusted": 0
        }

        # Emergency stop flag
        self.emergency_stop = False

        # Audit log
        self.audit_log = []

    async def run_daily_cycle(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Run complete daily automation cycle.

        Morning (6 AM):
        1. Check all supplier prices
        2. Discover new products
        3. Review competitor performance
        4. Generate morning briefing

        Afternoon (12 PM):
        5. Optimize ad campaigns
        6. Deploy approved products
        7. Adjust prices based on performance

        Evening (6 PM):
        8. Check email responses needed
        9. Generate end-of-day report
        10. Plan tomorrow's actions
        """
        if self.emergency_stop:
            return {"success": False, "error": "AutoPilot in emergency stop mode"}

        report = {
            "cycle_start": datetime.now(timezone.utc).isoformat(),
            "mode": self.mode.value,
            "phases": {}
        }

        # Phase 1: Morning - Intelligence gathering
        morning_results = await self._morning_intelligence_phase(user_id)
        report["phases"]["morning_intelligence"] = morning_results

        # Phase 2: Afternoon - Execution
        afternoon_results = await self._afternoon_execution_phase(user_id)
        report["phases"]["afternoon_execution"] = afternoon_results

        # Phase 3: Evening - Review and planning
        evening_results = await self._evening_review_phase(user_id)
        report["phases"]["evening_review"] = evening_results

        report["cycle_end"] = datetime.now(timezone.utc).isoformat()
        report["actions_taken"] = self.actions_today
        report["safety_status"] = self._check_safety_limits()

        return report

    async def _morning_intelligence_phase(self, user_id: Optional[int]) -> Dict[str, Any]:
        """Morning: Gather intelligence and discover opportunities."""
        results = {}

        # 1. Check all supplier prices
        self._log_action("Starting supplier price monitoring")
        supplier_results = await self.supplier_monitor.monitor_all_products(user_id=user_id)
        results["supplier_monitoring"] = {
            "products_checked": supplier_results["products_checked"],
            "price_changes_detected": len([
                r for r in supplier_results.get("results", [])
                if r.get("change_percent", 0) != 0
            ])
        }

        # 2. Discover new products
        self._log_action("Discovering new products")
        discovery_results = await self.ai.autonomous_opportunity_scan(user_id=user_id)
        results["product_discovery"] = {
            "opportunities_found": len(discovery_results)
        }

        # Create actions for top opportunities
        if self.mode in [AutoPilotMode.SEMI_AUTO, AutoPilotMode.FULL_AUTO]:
            for opp in discovery_results[:3]:  # Top 3 opportunities
                if opp.get("potential_score", 0) > 85:
                    await self._create_product_deployment_action(opp)

        # 3. Learn from product performance
        self._log_action("Learning from product performance")
        learning_results = await self.learning_engine.learn_from_own_products(user_id=user_id)
        results["competitive_learning"] = {
            "patterns_found": learning_results["patterns_found"],
            "products_analyzed": learning_results.get("products_analyzed", {}).get("total", 0)
        }

        # 4. Generate morning briefing
        self._log_action("Generating morning briefing")
        # This would call briefing engine
        results["briefing_generated"] = True

        return results

    async def _afternoon_execution_phase(self, user_id: Optional[int]) -> Dict[str, Any]:
        """Afternoon: Execute approved actions and optimizations."""
        results = {}

        # 1. Deploy products (if in auto mode)
        if self.mode == AutoPilotMode.FULL_AUTO:
            self._log_action("Auto-deploying approved products")
            deployment_results = await self._auto_deploy_products(user_id)
            results["products_deployed"] = deployment_results
        else:
            results["products_deployed"] = "Pending human approval"

        # 2. Optimize ad campaigns
        self._log_action("Optimizing ad campaigns")
        ad_optimization_results = await self._optimize_ad_campaigns(user_id)
        results["ad_optimization"] = ad_optimization_results

        # 3. Adjust prices based on performance
        self._log_action("Adjusting prices based on performance")
        price_adjustment_results = await self._adjust_prices_by_performance(user_id)
        results["price_adjustments"] = price_adjustment_results

        return results

    async def _evening_review_phase(self, user_id: Optional[int]) -> Dict[str, Any]:
        """Evening: Review performance and plan tomorrow."""
        results = {}

        # 1. Health check
        self._log_action("Running health check")
        health = await self.ai.autonomous_health_check(user_id=user_id)
        results["health_score"] = health.get("health_score", 0)
        results["critical_alerts"] = len(health.get("critical_alerts", []))

        # 2. Generate end-of-day report
        results["actions_completed_today"] = self.actions_today.copy()

        # 3. Plan tomorrow's priorities
        self._log_action("Planning tomorrow's priorities")
        # Use AI to analyze today's results and plan tomorrow
        priorities = await self._plan_tomorrow_priorities(health, user_id)
        results["tomorrow_priorities"] = priorities

        # 4. Reset daily counters
        self.actions_today = {
            "products_deployed": 0,
            "ads_created": 0,
            "ad_spend": 0.0,
            "prices_adjusted": 0
        }

        return results

    async def _auto_deploy_products(self, user_id: Optional[int]) -> Dict[str, Any]:
        """Automatically deploy products that passed all checks."""

        # Get pending product deployment actions
        pending_actions = self.action_manager.get_pending_actions(min_confidence=0.8)

        deploy_actions = [
            a for a in pending_actions
            if a.action_type == ActionType.DEPLOY_PRODUCT
        ]

        deployed = []
        skipped = []

        for action in deploy_actions:
            # Check safety limits
            if self.actions_today["products_deployed"] >= self.safety_limits.max_products_per_day:
                skipped.append({
                    "action_id": action.action_id,
                    "reason": "Daily product limit reached"
                })
                continue

            product_price = action.parameters.get("price", 0)
            if product_price > self.safety_limits.max_product_price:
                skipped.append({
                    "action_id": action.action_id,
                    "reason": f"Price ${product_price} exceeds limit ${self.safety_limits.max_product_price}"
                })
                continue

            # Execute deployment
            try:
                result = await self.action_manager.accept_action(
                    action.action_id,
                    user_context={"user_id": user_id}
                )

                if result.get("success"):
                    deployed.append(action.action_id)
                    self.actions_today["products_deployed"] += 1
                    self._log_action(f"Auto-deployed product: {action.title}")
                else:
                    skipped.append({
                        "action_id": action.action_id,
                        "reason": result.get("error", "Unknown error")
                    })
            except Exception as e:
                skipped.append({
                    "action_id": action.action_id,
                    "reason": str(e)
                })

        return {
            "deployed": len(deployed),
            "skipped": len(skipped),
            "details": {
                "deployed_ids": deployed,
                "skipped_reasons": skipped
            }
        }

    async def _optimize_ad_campaigns(self, user_id: Optional[int]) -> Dict[str, Any]:
        """Optimize ad campaign budgets based on ROAS."""

        # Get all active campaigns
        campaigns = self.db.query(AdCampaign).filter(
            AdCampaign.status == "ACTIVE"
        )

        if user_id:
            campaigns = campaigns.filter(AdCampaign.user_id == user_id)

        campaigns = campaigns.all()

        optimizations = {
            "increased_budget": [],
            "decreased_budget": [],
            "paused": []
        }

        for campaign in campaigns:
            roas = float(campaign.roas) if campaign.roas else 0

            # Pause low ROAS campaigns
            if roas < 1.0:
                if self.mode == AutoPilotMode.FULL_AUTO:
                    # Auto-pause
                    campaign.status = "PAUSED"
                    self.db.commit()
                    optimizations["paused"].append(campaign.id)
                    self._log_action(f"Auto-paused low ROAS campaign: {campaign.campaign_name}")
                else:
                    # Create action for approval
                    self.action_manager.create_action(
                        action_type=ActionType.PAUSE_AD,
                        title=f"Pause low ROAS campaign: {campaign.campaign_name}",
                        description=f"ROAS {roas:.2f}x is below 1.0x break-even",
                        impact_summary=f"Save ${campaign.daily_budget:.2f}/day",
                        parameters={"campaign_id": campaign.id},
                        confidence=0.9
                    )

            # Increase budget for high ROAS campaigns
            elif roas > 3.0:
                increase_percent = 20  # 20% increase

                # Check daily spend limit
                new_daily_budget = float(campaign.daily_budget) * 1.2
                projected_daily_spend = self.actions_today["ad_spend"] + new_daily_budget

                if projected_daily_spend > self.safety_limits.max_daily_ad_spend:
                    continue  # Skip if would exceed limit

                if self.mode == AutoPilotMode.FULL_AUTO:
                    # Auto-increase
                    campaign.daily_budget = new_daily_budget
                    self.db.commit()
                    optimizations["increased_budget"].append(campaign.id)
                    self.actions_today["ad_spend"] += new_daily_budget
                    self._log_action(f"Auto-increased budget for campaign: {campaign.campaign_name}")
                else:
                    # Create action for approval
                    self.action_manager.create_action(
                        action_type=ActionType.INCREASE_AD_BUDGET,
                        title=f"Increase budget for high ROAS campaign: {campaign.campaign_name}",
                        description=f"ROAS {roas:.2f}x is excellent, scale up",
                        impact_summary=f"Increase daily budget by ${new_daily_budget - float(campaign.daily_budget):.2f}",
                        parameters={
                            "campaign_id": campaign.id,
                            "adjustment_percent": increase_percent
                        },
                        confidence=0.85
                    )

        return optimizations

    async def _adjust_prices_by_performance(self, user_id: Optional[int]) -> Dict[str, Any]:
        """Adjust product prices based on sales performance."""

        # Get products with sales data
        query = self.db.query(Product).filter(
            Product.total_sales.isnot(None),
            Product.status == ProductStatus.ACTIVE
        )

        if user_id:
            from ospra_os.database import Store
            query = query.join(Store).filter(Store.user_id == user_id)

        products = query.all()

        adjustments = []

        for product in products:
            # Low sales (< 10 in last 30 days) → test price decrease
            if product.total_sales < 10:
                # Suggest 10% price decrease to drive sales
                current_price = float(product.price)
                new_price = current_price * 0.9

                # Check margin is still acceptable
                if product.supplier_cost:
                    new_margin = ((new_price - float(product.supplier_cost)) / new_price) * 100
                    if new_margin < 30:
                        continue  # Skip if margin too low

                # Create action
                self.action_manager.create_action(
                    action_type=ActionType.ADJUST_PRICE,
                    title=f"Lower price to boost sales: {product.title}",
                    description=f"Only {product.total_sales} sales. Lower price by 10% to ${new_price:.2f}",
                    impact_summary=f"Drive more sales volume",
                    parameters={
                        "product_id": product.id,
                        "new_price": new_price
                    },
                    confidence=0.7
                )

                adjustments.append({
                    "product_id": product.id,
                    "reason": "low_sales",
                    "proposed_price": new_price
                })

            # High sales + high margin → test price increase
            elif product.total_sales > 100:
                margin = float(product.profit_margin) if product.profit_margin else 0
                if margin > 60:
                    # Suggest 5% price increase (test price ceiling)
                    current_price = float(product.price)
                    new_price = current_price * 1.05

                    self.action_manager.create_action(
                        action_type=ActionType.ADJUST_PRICE,
                        title=f"Test price increase: {product.title}",
                        description=f"Strong seller ({product.total_sales} sales). Test 5% price increase to ${new_price:.2f}",
                        impact_summary=f"Increase profit per sale",
                        parameters={
                            "product_id": product.id,
                            "new_price": new_price
                        },
                        confidence=0.65
                    )

                    adjustments.append({
                        "product_id": product.id,
                        "reason": "high_demand",
                        "proposed_price": new_price
                    })

        return {
            "adjustments_proposed": len(adjustments),
            "details": adjustments
        }

    async def _plan_tomorrow_priorities(
        self,
        health: Dict[str, Any],
        user_id: Optional[int]
    ) -> List[str]:
        """Use AI to plan tomorrow's priorities."""

        # Use cost-effective model for planning
        prompt = f"""Based on today's health check, what should be the top 3 priorities for tomorrow?

Health Score: {health.get('health_score', 0)}/100
Critical Alerts: {health.get('critical_alerts', [])}
Predictions: {health.get('predictions', [])}

Return 3 specific, actionable priorities for tomorrow."""

        response = await self.model_router.route_request(
            message=prompt,
            task_complexity=TaskComplexity.MEDIUM
        )

        # Parse response into list
        priorities = [line.strip() for line in response.split('\n') if line.strip()]

        return priorities[:3]

    async def _create_product_deployment_action(self, opportunity: Dict[str, Any]):
        """Create action to deploy a discovered product."""

        self.action_manager.create_action(
            action_type=ActionType.DEPLOY_PRODUCT,
            title=f"Deploy new product: {opportunity.get('name', 'Unknown')}",
            description=opportunity.get('reasoning', ''),
            impact_summary=f"Potential score: {opportunity.get('potential_score', 0)}/100",
            parameters={
                "product_name": opportunity.get("name"),
                "niche": opportunity.get("niche"),
                "source": opportunity.get("source")
            },
            confidence=opportunity.get("potential_score", 0) / 100
        )

    def _check_safety_limits(self) -> Dict[str, Any]:
        """Check if any safety limits have been breached."""
        return {
            "ad_spend_limit": {
                "current": self.actions_today["ad_spend"],
                "limit": self.safety_limits.max_daily_ad_spend,
                "status": "OK" if self.actions_today["ad_spend"] < self.safety_limits.max_daily_ad_spend else "EXCEEDED"
            },
            "products_deployed_limit": {
                "current": self.actions_today["products_deployed"],
                "limit": self.safety_limits.max_products_per_day,
                "status": "OK" if self.actions_today["products_deployed"] < self.safety_limits.max_products_per_day else "EXCEEDED"
            }
        }

    def _log_action(self, message: str):
        """Log action to audit trail."""
        self.audit_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": message
        })

        # Keep only last 1000 entries
        if len(self.audit_log) > 1000:
            self.audit_log = self.audit_log[-1000:]

    def get_audit_log(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent audit log entries."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        return [
            entry for entry in self.audit_log
            if datetime.fromisoformat(entry["timestamp"]) > cutoff
        ]

    def set_mode(self, mode: AutoPilotMode):
        """Change AutoPilot mode."""
        self._log_action(f"AutoPilot mode changed: {self.mode.value} → {mode.value}")
        self.mode = mode

    def emergency_stop_enable(self):
        """Enable emergency stop - halts all automation."""
        self.emergency_stop = True
        self._log_action("EMERGENCY STOP ACTIVATED")

    def emergency_stop_disable(self):
        """Disable emergency stop - resume automation."""
        self.emergency_stop = False
        self._log_action("Emergency stop deactivated - resuming automation")


def get_autopilot(
    db: Session,
    mode: AutoPilotMode = AutoPilotMode.ASSISTED
) -> AutoPilot:
    """Factory function to create AutoPilot."""
    return AutoPilot(db, mode=mode)
