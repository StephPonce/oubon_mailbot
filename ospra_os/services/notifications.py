"""
Customer notification system
Handles alerts for at-risk customers, high-value changes, and important events
"""
import logging
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum
import json

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """Notification types"""
    AT_RISK_CUSTOMER = "at_risk_customer"
    HIGH_CHURN_ALERT = "high_churn_alert"
    SEGMENT_CHANGE = "segment_change"
    HIGH_VALUE_CUSTOMER = "high_value_customer"
    CUSTOMER_LOST = "customer_lost"
    NEW_CHAMPION = "new_champion"
    LTV_MILESTONE = "ltv_milestone"
    # Competitive Intelligence
    COMPETITOR_PRICE_DROP = "competitor_price_drop"
    COMPETITOR_NEW_PRODUCT = "competitor_new_product"
    COMPETITOR_ADDED = "competitor_added"
    PRICING_OPPORTUNITY = "pricing_opportunity"
    COMPETITIVE_THREAT = "competitive_threat"
    MARKET_GAP_FOUND = "market_gap_found"


class NotificationChannel(str, Enum):
    """Notification delivery channels"""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    IN_APP = "in_app"


class NotificationPriority(str, Enum):
    """Notification priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CustomerNotification:
    """
    Manages customer-related notifications
    """

    def __init__(self):
        self.notifications_log = []

    async def send_at_risk_alert(
        self,
        customer: Dict,
        churn_probability: float,
        risk_factors: List[str],
        recommended_actions: List[str],
        channels: List[NotificationChannel] = None
    ):
        """
        Send alert for at-risk customer
        """
        if channels is None:
            channels = [NotificationChannel.SLACK, NotificationChannel.EMAIL]

        notification = {
            "type": NotificationType.AT_RISK_CUSTOMER,
            "priority": NotificationPriority.HIGH if churn_probability > 0.7 else NotificationPriority.MEDIUM,
            "customer_id": customer.get("customer_id"),
            "customer_name": f"{customer.get('first_name')} {customer.get('last_name')}",
            "customer_email": customer.get("email"),
            "churn_probability": churn_probability,
            "ltv": customer.get("ltv", 0),
            "risk_factors": risk_factors,
            "recommended_actions": recommended_actions,
            "timestamp": datetime.now().isoformat(),
            "channels": channels
        }

        await self._send_notification(notification)

    async def send_high_value_alert(
        self,
        customer: Dict,
        new_ltv: float,
        previous_ltv: float,
        channels: List[NotificationChannel] = None
    ):
        """
        Send alert for high-value customer milestone
        """
        if channels is None:
            channels = [NotificationChannel.SLACK, NotificationChannel.IN_APP]

        ltv_increase = new_ltv - previous_ltv
        percentage_increase = (ltv_increase / previous_ltv) * 100 if previous_ltv > 0 else 0

        notification = {
            "type": NotificationType.HIGH_VALUE_CUSTOMER,
            "priority": NotificationPriority.MEDIUM,
            "customer_id": customer.get("customer_id"),
            "customer_name": f"{customer.get('first_name')} {customer.get('last_name')}",
            "customer_email": customer.get("email"),
            "new_ltv": new_ltv,
            "previous_ltv": previous_ltv,
            "ltv_increase": ltv_increase,
            "percentage_increase": percentage_increase,
            "message": f"Customer LTV increased by ${ltv_increase:.2f} ({percentage_increase:.1f}%)",
            "timestamp": datetime.now().isoformat(),
            "channels": channels
        }

        await self._send_notification(notification)

    async def send_segment_change_alert(
        self,
        customer: Dict,
        old_segment: str,
        new_segment: str,
        channels: List[NotificationChannel] = None
    ):
        """
        Send alert when customer segment changes
        """
        if channels is None:
            channels = [NotificationChannel.IN_APP]

        # Determine priority based on segment change
        critical_changes = [
            ("CHAMPION", "AT_RISK"),
            ("LOYAL", "AT_RISK"),
            ("CHAMPION", "LOST"),
            ("LOYAL", "LOST")
        ]
        positive_changes = [
            ("NEW_CUSTOMER", "CHAMPION"),
            ("POTENTIAL_LOYALIST", "CHAMPION"),
            ("AT_RISK", "LOYAL")
        ]

        if (old_segment, new_segment) in critical_changes:
            priority = NotificationPriority.CRITICAL
        elif (old_segment, new_segment) in positive_changes:
            priority = NotificationPriority.LOW
        else:
            priority = NotificationPriority.MEDIUM

        notification = {
            "type": NotificationType.SEGMENT_CHANGE,
            "priority": priority,
            "customer_id": customer.get("customer_id"),
            "customer_name": f"{customer.get('first_name')} {customer.get('last_name')}",
            "customer_email": customer.get("email"),
            "old_segment": old_segment,
            "new_segment": new_segment,
            "ltv": customer.get("ltv", 0),
            "message": f"Customer moved from {old_segment} to {new_segment}",
            "timestamp": datetime.now().isoformat(),
            "channels": channels
        }

        await self._send_notification(notification)

    async def send_new_champion_alert(
        self,
        customer: Dict,
        channels: List[NotificationChannel] = None
    ):
        """
        Send alert when customer becomes a Champion
        """
        if channels is None:
            channels = [NotificationChannel.SLACK, NotificationChannel.EMAIL]

        notification = {
            "type": NotificationType.NEW_CHAMPION,
            "priority": NotificationPriority.LOW,
            "customer_id": customer.get("customer_id"),
            "customer_name": f"{customer.get('first_name')} {customer.get('last_name')}",
            "customer_email": customer.get("email"),
            "ltv": customer.get("ltv", 0),
            "order_count": customer.get("order_count", 0),
            "message": "New Champion customer! Consider VIP treatment.",
            "timestamp": datetime.now().isoformat(),
            "channels": channels
        }

        await self._send_notification(notification)

    async def send_customer_lost_alert(
        self,
        customer: Dict,
        days_since_last_order: int,
        channels: List[NotificationChannel] = None
    ):
        """
        Send alert when customer is classified as LOST
        """
        if channels is None:
            channels = [NotificationChannel.SLACK]

        notification = {
            "type": NotificationType.CUSTOMER_LOST,
            "priority": NotificationPriority.MEDIUM,
            "customer_id": customer.get("customer_id"),
            "customer_name": f"{customer.get('first_name')} {customer.get('last_name')}",
            "customer_email": customer.get("email"),
            "ltv": customer.get("ltv", 0),
            "days_since_last_order": days_since_last_order,
            "message": f"Customer lost - {days_since_last_order} days since last order",
            "recommended_action": "Consider win-back campaign",
            "timestamp": datetime.now().isoformat(),
            "channels": channels
        }

        await self._send_notification(notification)

    # ========================================================================
    # COMPETITIVE INTELLIGENCE NOTIFICATIONS
    # ========================================================================

    async def send_competitor_price_drop_alert(
        self,
        competitor_name: str,
        product_name: str,
        old_price: float,
        new_price: float,
        drop_percent: float,
        our_price: Optional[float] = None,
        channels: List[NotificationChannel] = None
    ):
        """Send alert when competitor drops price significantly"""
        if channels is None:
            channels = [NotificationChannel.SLACK, NotificationChannel.IN_APP]

        priority = NotificationPriority.HIGH if drop_percent >= 25 else NotificationPriority.MEDIUM

        message = f"{competitor_name} dropped price on {product_name} by {drop_percent:.1f}% (${old_price:.2f} → ${new_price:.2f})"
        if our_price:
            message += f". We're priced at ${our_price:.2f}"

        notification = {
            "type": NotificationType.COMPETITOR_PRICE_DROP,
            "priority": priority,
            "competitor_name": competitor_name,
            "product_name": product_name,
            "old_price": old_price,
            "new_price": new_price,
            "drop_percent": drop_percent,
            "our_price": our_price,
            "message": message,
            "recommended_action": "Consider price adjustment or value differentiation",
            "timestamp": datetime.now().isoformat(),
            "channels": channels
        }

        await self._send_notification(notification)

    async def send_competitor_new_product_alert(
        self,
        competitor_name: str,
        product_name: str,
        product_price: float,
        estimated_demand: str,
        channels: List[NotificationChannel] = None
    ):
        """Send alert when competitor adds new product"""
        if channels is None:
            channels = [NotificationChannel.IN_APP]

        notification = {
            "type": NotificationType.COMPETITOR_NEW_PRODUCT,
            "priority": NotificationPriority.LOW,
            "competitor_name": competitor_name,
            "product_name": product_name,
            "product_price": product_price,
            "estimated_demand": estimated_demand,
            "message": f"{competitor_name} added new product: {product_name} (${product_price:.2f})",
            "recommended_action": "Research if this product fits our catalog",
            "timestamp": datetime.now().isoformat(),
            "channels": channels
        }

        await self._send_notification(notification)

    async def send_pricing_opportunity_alert(
        self,
        product_name: str,
        our_price: float,
        market_avg_price: float,
        opportunity_type: str,
        potential_impact: float,
        channels: List[NotificationChannel] = None
    ):
        """Send alert for pricing opportunities"""
        if channels is None:
            channels = [NotificationChannel.SLACK, NotificationChannel.IN_APP]

        priority = NotificationPriority.HIGH if potential_impact >= 20 else NotificationPriority.MEDIUM

        if opportunity_type == "PRICE_INCREASE":
            message = f"Opportunity to raise price on {product_name}. We're {potential_impact:.1f}% cheaper than market avg"
        else:
            message = f"Consider lowering price on {product_name}. We're {potential_impact:.1f}% higher than market avg"

        notification = {
            "type": NotificationType.PRICING_OPPORTUNITY,
            "priority": priority,
            "product_name": product_name,
            "our_price": our_price,
            "market_avg_price": market_avg_price,
            "opportunity_type": opportunity_type,
            "potential_impact": potential_impact,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "channels": channels
        }

        await self._send_notification(notification)

    async def send_market_gap_alert(
        self,
        gap_type: str,
        product_name: str,
        competitors_carrying: int,
        avg_price: float,
        opportunity_score: int,
        channels: List[NotificationChannel] = None
    ):
        """Send alert for market gaps"""
        if channels is None:
            channels = [NotificationChannel.SLACK, NotificationChannel.IN_APP]

        priority = NotificationPriority.HIGH if opportunity_score >= 80 else NotificationPriority.MEDIUM

        notification = {
            "type": NotificationType.MARKET_GAP_FOUND,
            "priority": priority,
            "gap_type": gap_type,
            "product_name": product_name,
            "competitors_carrying": competitors_carrying,
            "avg_price": avg_price,
            "opportunity_score": opportunity_score,
            "message": f"Market gap: {product_name} carried by {competitors_carrying} competitors at ~${avg_price:.2f}. Opportunity score: {opportunity_score}/100",
            "recommended_action": "Consider adding to catalog",
            "timestamp": datetime.now().isoformat(),
            "channels": channels
        }

        await self._send_notification(notification)

    async def _send_notification(self, notification: Dict):
        """
        Internal method to send notification through configured channels
        """
        logger.info(f"📬 Sending {notification['type']} notification for customer {notification.get('customer_name')}")

        # Log notification
        self.notifications_log.append(notification)

        # Send through each channel
        for channel in notification.get('channels', []):
            if channel == NotificationChannel.EMAIL:
                await self._send_email(notification)
            elif channel == NotificationChannel.SLACK:
                await self._send_slack(notification)
            elif channel == NotificationChannel.WEBHOOK:
                await self._send_webhook(notification)
            elif channel == NotificationChannel.IN_APP:
                await self._save_in_app_notification(notification)

    async def _send_email(self, notification: Dict):
        """
        Send email notification
        """
        # TODO: Integrate with email service (e.g., SendGrid, AWS SES)
        logger.info(f"  📧 Email notification sent to {notification.get('customer_email')}")

    async def _send_slack(self, notification: Dict):
        """
        Send Slack notification
        """
        # TODO: Integrate with Slack webhook
        slack_message = self._format_slack_message(notification)
        logger.info(f"  💬 Slack notification sent: {slack_message}")

    async def _send_webhook(self, notification: Dict):
        """
        Send webhook notification
        """
        # TODO: Send to configured webhook URL
        logger.info(f"  🔗 Webhook notification sent")

    async def _save_in_app_notification(self, notification: Dict):
        """
        Save in-app notification to database
        """
        # TODO: Save to database for in-app notification center
        logger.info(f"  🔔 In-app notification saved")

    def _format_slack_message(self, notification: Dict) -> str:
        """
        Format notification for Slack
        """
        type_emojis = {
            NotificationType.AT_RISK_CUSTOMER: "⚠️",
            NotificationType.HIGH_CHURN_ALERT: "🚨",
            NotificationType.SEGMENT_CHANGE: "🔄",
            NotificationType.HIGH_VALUE_CUSTOMER: "💰",
            NotificationType.CUSTOMER_LOST: "😢",
            NotificationType.NEW_CHAMPION: "🏆",
            NotificationType.LTV_MILESTONE: "🎯"
        }

        emoji = type_emojis.get(notification['type'], "📢")
        customer_name = notification.get('customer_name', 'Unknown')
        message = notification.get('message', '')

        return f"{emoji} {customer_name}: {message}"

    def get_recent_notifications(self, limit: int = 50) -> List[Dict]:
        """
        Get recent notifications
        """
        return self.notifications_log[-limit:]

    def get_notifications_by_type(
        self,
        notification_type: NotificationType,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get notifications by type
        """
        filtered = [
            n for n in self.notifications_log
            if n['type'] == notification_type
        ]
        return filtered[-limit:]

    def get_notifications_by_customer(
        self,
        customer_id: str,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get notifications for a specific customer
        """
        filtered = [
            n for n in self.notifications_log
            if n.get('customer_id') == customer_id
        ]
        return filtered[-limit:]


# Global notification service instance
_notification_service: Optional[CustomerNotification] = None


def get_notification_service() -> CustomerNotification:
    """
    Get or create the global notification service instance
    """
    global _notification_service
    if _notification_service is None:
        _notification_service = CustomerNotification()
    return _notification_service


async def send_at_risk_alert(customer: Dict, churn_probability: float, risk_factors: List[str], recommended_actions: List[str]):
    """
    Convenience function to send at-risk customer alert
    """
    service = get_notification_service()
    await service.send_at_risk_alert(customer, churn_probability, risk_factors, recommended_actions)


async def send_segment_change_alert(customer: Dict, old_segment: str, new_segment: str):
    """
    Convenience function to send segment change alert
    """
    service = get_notification_service()
    await service.send_segment_change_alert(customer, old_segment, new_segment)
