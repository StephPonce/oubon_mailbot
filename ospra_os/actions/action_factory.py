"""
Action Factory - Convert AI insights into pending Actions

Automatically creates Actions from:
- Product discoveries
- Price alerts
- Ad performance issues
- Inventory warnings
- Email responses

Now with Auto-Pilot integration (GROK RECOMMENDATION #7):
- High-confidence actions (≥85%) can be automatically executed
- User-configurable thresholds and safety limits
- Complete audit trail of auto-execution decisions
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from ospra_os.database.action_models import Action, AIActionType, AIActionStatus
from ospra_os.actions.auto_pilot import AutoPilotEngine


class ActionFactory:
    """Factory for creating different types of actions from AI insights"""

    def __init__(self, db: Session, user_id: int, store_id: Optional[int] = None):
        self.db = db
        self.user_id = user_id
        self.store_id = store_id

    def create_action(
        self,
        action_type: AIActionType,
        title: str,
        description: str,
        confidence: float,
        rationale: str,
        factors: List[Dict[str, Any]],
        payload: Dict[str, Any],
        estimated_impact: Optional[str] = None,
        product_image: Optional[str] = None,
        expires_in_hours: int = 72,
        check_auto_pilot: bool = True
    ) -> Dict[str, Any]:
        """
        Create and save a new action.

        With Auto-Pilot integration:
        - If check_auto_pilot=True (default), evaluates action for auto-execution
        - High-confidence actions may be automatically approved/executed
        - Returns dict with action and auto_pilot_result

        Returns:
            Dict with keys:
            - action: The created Action object
            - auto_pilot_result: Auto-pilot decision (if enabled)
        """

        action = Action(
            user_id=self.user_id,
            store_id=self.store_id,
            action_type=action_type,
            title=title,
            description=description,
            confidence=confidence,
            rationale=rationale,
            factors=factors,
            payload=payload,
            estimated_impact=estimated_impact,
            product_image=product_image,
            expires_at=datetime.utcnow() + timedelta(hours=expires_in_hours),
            status=AIActionStatus.PENDING
        )

        self.db.add(action)
        self.db.commit()
        self.db.refresh(action)

        # Auto-Pilot Integration (GROK #7)
        auto_pilot_result = None
        if check_auto_pilot:
            auto_pilot_result = self._check_auto_pilot(action)

        return {
            "action": action,
            "auto_pilot_result": auto_pilot_result
        }

    def _check_auto_pilot(self, action: Action) -> Dict[str, Any]:
        """
        Check if action should be auto-executed via Auto-Pilot.
        Returns auto-pilot decision result.
        """
        try:
            engine = AutoPilotEngine(db=self.db, user_id=self.user_id)

            # Check if action can be auto-executed
            can_execute, reason = engine.can_auto_execute(action)

            action_type_str = action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)

            # Log the decision
            from ospra_os.database import AutoPilotLog
            log = AutoPilotLog(
                user_id=self.user_id,
                action_id=action.id,
                confidence=action.confidence,
                threshold_used=engine.get_threshold_for_action(action_type_str),
                executed=can_execute,
                skipped_reason=None if can_execute else reason
            )
            self.db.add(log)

            # If approved, mark action as auto-approved
            if can_execute:
                action.status = AIActionStatus.APPROVED
                action.approved_at = datetime.utcnow()
                action.approved_by = "auto_pilot"
                # Note: Actual execution would happen in a separate executor service

            self.db.commit()

            if can_execute:
                return {
                    "auto_executed": True,
                    "action_id": action.id,
                    "reason": "confidence_threshold_met",
                    "message": f"Auto-approved with {action.confidence}% confidence",
                    "confidence": action.confidence,
                    "threshold": engine.get_threshold_for_action(action_type_str)
                }
            else:
                return {
                    "auto_executed": False,
                    "action_id": action.id,
                    "reason": reason,
                    "threshold": engine.get_threshold_for_action(action_type_str),
                    "confidence": action.confidence,
                    "message": f"Action queued for manual review: {reason}"
                }

        except Exception as e:
            # If auto-pilot fails, just log and continue with normal flow
            print(f"Auto-pilot check failed for action {action.id}: {e}")
            return {
                "auto_executed": False,
                "action_id": action.id,
                "reason": "auto_pilot_error",
                "message": f"Auto-pilot check failed, action pending manual review"
            }

    def queue_product_deployment(
        self,
        product_id: str,
        product_name: str,
        source_price: float,
        suggested_sell_price: float,
        niche: str,
        ai_score: float,
        velocity_score: float = 50,
        saturation_score: float = 50,
        images: List[str] = None,
        rationale: str = None
    ) -> Action:
        """Queue a product for deployment to Shopify"""

        margin = ((suggested_sell_price - source_price) / suggested_sell_price) * 100
        confidence = min(95, max(40, ai_score))

        # Build factors based on product metrics
        factors = []

        if velocity_score > 80:
            factors.append({"label": "High velocity", "value": 18.0, "icon": "trending_up"})
        elif velocity_score > 60:
            factors.append({"label": "Good velocity", "value": 10.0, "icon": "trending_up"})

        if margin > 50:
            factors.append({"label": "Excellent margin", "value": 20.0, "icon": "dollar_sign"})
        elif margin > 35:
            factors.append({"label": "Good margin", "value": 12.0, "icon": "dollar_sign"})

        if saturation_score < 30:
            factors.append({"label": "Low competition", "value": 15.0, "icon": "check_circle"})
        elif saturation_score > 70:
            factors.append({"label": "High competition", "value": -10.0, "icon": "alert_triangle"})

        # Build rationale if not provided
        if not rationale:
            rationale = self._generate_deployment_rationale(
                product_name, velocity_score, margin, saturation_score, ai_score
            )

        # Estimate impact
        estimated_monthly_sales = max(5, int(velocity_score / 10))
        profit_per_sale = suggested_sell_price - source_price
        estimated_impact = f"+${estimated_monthly_sales * profit_per_sale:.0f} projected monthly profit"

        return self.create_action(
            action_type=AIActionType.DEPLOY_PRODUCT,
            title=f"Deploy: {product_name}",
            description=f"Deploy to Shopify at ${suggested_sell_price:.2f} ({margin:.0f}% margin)",
            confidence=confidence,
            rationale=rationale,
            factors=factors,
            payload={
                "product_id": product_id,
                "product_name": product_name,
                "source_price": source_price,
                "sell_price": suggested_sell_price,
                "margin": round(margin, 1),
                "niche": niche,
                "images": images or [],
                "ai_score": ai_score,
                "velocity_score": velocity_score,
                "saturation_score": saturation_score
            },
            estimated_impact=estimated_impact,
            product_image=images[0] if images else None
        )

    def queue_price_adjustment(
        self,
        product_id: str,
        product_name: str,
        current_price: float,
        new_price: float,
        old_supplier_price: float,
        new_supplier_price: float,
        reason: str = "supplier_price_change"
    ) -> Action:
        """Queue a price adjustment"""

        new_margin = ((new_price - new_supplier_price) / new_price) * 100
        price_change_pct = ((new_price - current_price) / current_price) * 100

        factors = [
            {"label": "Margin protection", "value": 15.0, "icon": "shield"},
        ]

        if price_change_pct > 15:
            factors.append({"label": "Large increase", "value": -5.0, "icon": "alert_triangle"})

        rationale = f"Supplier price changed from ${old_supplier_price:.2f} to ${new_supplier_price:.2f}. "
        rationale += f"Recommended price adjustment maintains {new_margin:.0f}% margin while staying competitive."

        return self.create_action(
            action_type=AIActionType.ADJUST_PRICE,
            title=f"Price Adjustment: {product_name}",
            description=f"Adjust from ${current_price:.2f} to ${new_price:.2f}",
            confidence=82.0,
            rationale=rationale,
            factors=factors,
            payload={
                "product_id": product_id,
                "product_name": product_name,
                "current_price": current_price,
                "new_price": new_price,
                "old_supplier_price": old_supplier_price,
                "new_supplier_price": new_supplier_price,
                "new_margin": round(new_margin, 1),
                "reason": reason
            },
            estimated_impact=f"Maintain {new_margin:.0f}% profit margin"
        )

    def queue_pause_ad(
        self,
        campaign_id: str,
        campaign_name: str,
        platform: str,
        current_roas: float,
        spend_last_7d: float,
        conversions: int
    ) -> Action:
        """Queue pausing an underperforming ad"""

        factors = [
            {"label": "ROAS below target", "value": -25.0, "icon": "alert_triangle"},
            {"label": "High CPA", "value": -15.0, "icon": "alert_triangle"},
        ]

        weekly_savings = spend_last_7d

        rationale = f"Campaign ROAS is {current_roas:.1f}x, below 1.0x threshold. "
        rationale += f"Spent ${spend_last_7d:.2f} with only {conversions} conversions in 7 days. "
        rationale += "Recommend pausing to prevent further loss."

        return self.create_action(
            action_type=AIActionType.PAUSE_AD,
            title=f"Pause Ad: {campaign_name}",
            description=f"ROAS dropped to {current_roas:.1f}x over 7 days",
            confidence=94.0,
            rationale=rationale,
            factors=factors,
            payload={
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "platform": platform,
                "current_roas": current_roas,
                "spend_last_7d": spend_last_7d,
                "conversions": conversions
            },
            estimated_impact=f"Save ${weekly_savings:.0f}/week in ad spend"
        )

    def queue_drop_product(
        self,
        product_id: str,
        product_name: str,
        days_listed: int,
        total_sales: int,
        total_revenue: float,
        return_rate: float = 0
    ) -> Action:
        """Queue removing an underperforming product"""

        factors = []
        confidence = 70.0

        if total_sales == 0 and days_listed > 30:
            factors.append({"label": "Zero sales in 30+ days", "value": -30.0, "icon": "alert_triangle"})
            confidence = 90.0

        if return_rate > 20:
            factors.append({"label": "High return rate", "value": -20.0, "icon": "alert_triangle"})
            confidence = min(95.0, confidence + 10)

        rationale = f"Product has been listed for {days_listed} days with {total_sales} sales. "
        if return_rate > 0:
            rationale += f"Return rate is {return_rate:.0f}%. "
        rationale += "Recommend removing to focus on better performers."

        return self.create_action(
            action_type=AIActionType.DROP_PRODUCT,
            title=f"Drop Product: {product_name}",
            description=f"Underperforming - {total_sales} sales in {days_listed} days",
            confidence=confidence,
            rationale=rationale,
            factors=factors,
            payload={
                "product_id": product_id,
                "product_name": product_name,
                "days_listed": days_listed,
                "total_sales": total_sales,
                "total_revenue": total_revenue,
                "return_rate": return_rate
            },
            estimated_impact="Free up ad spend for better products"
        )

    def queue_email_reply(
        self,
        email_id: str,
        from_email: str,
        subject: str,
        draft_response: str,
        category: str,
        urgency: str = "normal"
    ) -> Action:
        """Queue an email reply for approval"""

        confidence = 75.0 if urgency == "normal" else 85.0

        factors = []
        if category == "refund":
            factors.append({"label": "Refund request", "value": 10.0, "icon": "alert_triangle"})
        elif category == "tracking":
            factors.append({"label": "Tracking inquiry", "value": 5.0, "icon": "package"})

        return self.create_action(
            action_type=AIActionType.REPLY_EMAIL,
            title=f"Reply: {subject[:50]}...",
            description=f"Respond to {from_email}",
            confidence=confidence,
            rationale=f"Auto-generated {category} response ready for review.",
            factors=factors,
            payload={
                "email_id": email_id,
                "from_email": from_email,
                "subject": subject,
                "draft_response": draft_response,
                "category": category,
                "urgency": urgency
            },
            estimated_impact="Faster response time"
        )

    def queue_restock_alert(
        self,
        product_id: str,
        product_name: str,
        current_stock: int,
        avg_daily_sales: float,
        days_until_stockout: int,
        reorder_quantity: int,
        supplier_url: str = ""
    ) -> Action:
        """Queue a restock recommendation"""

        urgency = "high" if days_until_stockout < 3 else "normal"
        confidence = 90.0 if urgency == "high" else 75.0

        factors = [
            {"label": f"{days_until_stockout} days until stockout", "value": -15.0, "icon": "alert_triangle"},
            {"label": f"{avg_daily_sales:.1f} daily sales", "value": 10.0, "icon": "trending_up"},
        ]

        return self.create_action(
            action_type=AIActionType.RESTOCK_ALERT,
            title=f"Restock: {product_name}",
            description=f"Low stock - {current_stock} units, {days_until_stockout} days left",
            confidence=confidence,
            rationale=f"Based on {avg_daily_sales:.1f} avg daily sales, stock will run out in {days_until_stockout} days. Recommend ordering {reorder_quantity} units.",
            factors=factors,
            payload={
                "product_id": product_id,
                "product_name": product_name,
                "current_stock": current_stock,
                "avg_daily_sales": avg_daily_sales,
                "days_until_stockout": days_until_stockout,
                "reorder_quantity": reorder_quantity,
                "supplier_url": supplier_url
            },
            estimated_impact="Prevent stockout and lost sales"
        )

    def _generate_deployment_rationale(
        self,
        product_name: str,
        velocity: float,
        margin: float,
        saturation: float,
        score: float
    ) -> str:
        """Generate a rationale string for product deployment"""

        parts = []

        if velocity > 80:
            parts.append("high demand velocity")
        elif velocity > 60:
            parts.append("steady demand")

        if margin > 50:
            parts.append(f"excellent {margin:.0f}% profit margin")
        elif margin > 35:
            parts.append(f"solid {margin:.0f}% margin")

        if saturation < 30:
            parts.append("low market saturation")

        if parts:
            rationale = f"This product shows {', '.join(parts)}. "
        else:
            rationale = f"This product meets baseline criteria. "

        if score > 85:
            rationale += "Strong buy signal based on multi-source validation."
        elif score > 70:
            rationale += "Good opportunity with moderate confidence."
        else:
            rationale += "Consider testing with limited inventory first."

        return rationale
