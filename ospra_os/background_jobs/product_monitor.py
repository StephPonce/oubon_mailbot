"""
📊 PRODUCT MONITORING BACKGROUND JOB
Tracks product changes and sends notifications using SQLite database
"""

import time
import logging
from datetime import datetime
from typing import List, Dict
from ospra_os.database.product_history import ProductHistoryDB
from ospra_os.intelligence.product_intelligence import ProductIntelligenceEngine
from ospra_os.notifications.email_notifier import EmailNotifier
from ospra_os.notifications.slack_notifier import SlackNotifier

logger = logging.getLogger(__name__)


class ProductMonitor:
    """Monitor products for changes and send notifications"""

    def __init__(self):
        self.db = ProductHistoryDB()
        self.discovery = ProductIntelligenceEngine()
        self.email_notifier = EmailNotifier()
        self.slack_notifier = SlackNotifier()
        logger.info("✅ Product monitor initialized with notifications")

    def check_all_products(self, niches: List[str] = None) -> List[Dict]:
        """
        Check all products for changes - run every 6 hours

        Args:
            niches: List of niches to check (default: all common niches)

        Returns:
            List of detected changes
        """
        if niches is None:
            niches = ['smart_home', 'fitness', 'kitchen', 'beauty', 'pet']

        logger.info("🔍 Starting product change detection...")

        all_changes = []

        for niche in niches:
            logger.info(f"Checking {niche} products...")

            try:
                # Get current products
                products = self.discovery.discover_products_by_niche(niche=niche, count=20)

                for product in products:
                    changes = self.check_product(product)
                    if changes:
                        all_changes.extend(changes)

            except Exception as e:
                logger.error(f"Error checking {niche}: {e}")
                continue

        logger.info(f"✅ Scan complete. {len(all_changes)} changes detected.")

        # Send notifications if changes detected
        if all_changes:
            # Send email notification
            email_sent = self.email_notifier.send_change_alert(all_changes)
            if email_sent:
                logger.info("📧 Email notification sent")

            # Send Slack notification
            slack_sent = self.slack_notifier.send_change_alert(all_changes)
            if slack_sent:
                logger.info("💬 Slack notification sent")

        return all_changes

    def check_product(self, current_product: Dict) -> List[Dict]:
        """
        Compare current product data with last snapshot

        Args:
            current_product: Current product data

        Returns:
            List of detected changes
        """
        product_id = current_product.get('id', current_product.get('product_id', 'unknown'))
        product_name = current_product.get('name', current_product.get('title', 'Unknown Product'))

        # Get last snapshot
        last_snapshot = self.db.get_latest_snapshot(product_id)

        if not last_snapshot:
            # First time seeing this product - save baseline
            self.db.save_snapshot(current_product)
            logger.debug(f"Saved baseline for new product: {product_name}")
            return []

        changes = []

        # Check velocity change (defensive access)
        old_velocity = last_snapshot.get('velocity_score', last_snapshot.get('velocity', 0)) or 0
        new_velocity = current_product.get('velocity_score', current_product.get('velocity', 0)) or 0

        if abs(old_velocity - new_velocity) >= 15:
            severity = "high" if abs(old_velocity - new_velocity) >= 30 else "medium"

            self.db.log_change(
                product_id=product_id,
                product_name=product_name,
                change_type="velocity",
                old_value=str(old_velocity),
                new_value=str(new_velocity),
                severity=severity
            )

            emoji = "📈" if new_velocity > old_velocity else "📉"
            changes.append({
                "product_name": product_name,
                "product_id": product_id,
                "type": "velocity",
                "old": old_velocity,
                "new": new_velocity,
                "severity": severity,
                "message": f"{emoji} Velocity: {old_velocity} → {new_velocity}"
            })

            logger.info(f"Velocity change detected: {product_name} ({old_velocity} → {new_velocity})")

        # Check price change (defensive access)
        old_price = last_snapshot.get('price', 0) or 0
        new_price = current_product.get('price', 0) or 0

        if abs(old_price - new_price) >= 5:
            severity = "high" if abs(old_price - new_price) >= 20 else "medium"

            self.db.log_change(
                product_id=product_id,
                product_name=product_name,
                change_type="price",
                old_value=f"${old_price:.2f}",
                new_value=f"${new_price:.2f}",
                severity=severity
            )

            emoji = "💰" if new_price > old_price else "💸"
            changes.append({
                "product_name": product_name,
                "product_id": product_id,
                "type": "price",
                "old": old_price,
                "new": new_price,
                "severity": severity,
                "message": f"{emoji} Price: ${old_price:.2f} → ${new_price:.2f}"
            })

            logger.info(f"Price change detected: {product_name} (${old_price} → ${new_price})")

        # Check score change (if available)
        if 'score' in current_product and 'score' in last_snapshot:
            old_score = last_snapshot.get('score', 0)
            new_score = current_product.get('score', 0)

            if abs(old_score - new_score) >= 2:
                severity = "low"

                self.db.log_change(
                    product_id=product_id,
                    product_name=product_name,
                    change_type="score",
                    old_value=f"{old_score:.1f}",
                    new_value=f"{new_score:.1f}",
                    severity=severity
                )

                emoji = "⭐" if new_score > old_score else "⚠️"
                changes.append({
                    "product_name": product_name,
                    "product_id": product_id,
                    "type": "score",
                    "old": old_score,
                    "new": new_score,
                    "severity": severity,
                    "message": f"{emoji} Score: {old_score:.1f} → {new_score:.1f}"
                })

        # Save new snapshot if changes detected
        if changes:
            self.db.save_snapshot(current_product)

        return changes

    def format_notification(self, changes: List[Dict]) -> str:
        """
        Format changes into notification message

        Args:
            changes: List of detected changes

        Returns:
            Formatted notification text
        """
        if not changes:
            return None

        # Group by severity
        high_priority = [c for c in changes if c['severity'] == 'high']
        medium_priority = [c for c in changes if c['severity'] == 'medium']
        low_priority = [c for c in changes if c['severity'] == 'low']

        message = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚨 PRODUCT CHANGE ALERT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total Changes: {len(changes)}
Scan Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

"""

        if high_priority:
            message += f"🔴 HIGH PRIORITY ({len(high_priority)}):\n"
            for change in high_priority:
                message += f"  • {change['product_name']}\n"
                message += f"    {change['message']}\n"
            message += "\n"

        if medium_priority:
            message += f"🟡 MEDIUM PRIORITY ({len(medium_priority)}):\n"
            for change in medium_priority[:5]:  # Limit to 5
                message += f"  • {change['product_name']}: {change['message']}\n"
            if len(medium_priority) > 5:
                message += f"  ... and {len(medium_priority) - 5} more\n"
            message += "\n"

        if low_priority:
            message += f"🟢 LOW PRIORITY ({len(low_priority)}):\n"
            for change in low_priority[:3]:  # Limit to 3
                message += f"  • {change['product_name']}: {change['message']}\n"
            if len(low_priority) > 3:
                message += f"  ... and {len(low_priority) - 3} more\n"

        message += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

        return message

    def get_stats(self) -> Dict:
        """Get monitoring statistics"""
        return self.db.get_stats()


def run_monitoring_loop(interval_hours: int = 6):
    """
    Background job - run product monitoring in a loop

    Args:
        interval_hours: Hours between each check (default: 6)
    """
    monitor = ProductMonitor()

    logger.info(f"🚀 Product monitoring started (checking every {interval_hours} hours)")

    while True:
        try:
            # Check all products
            changes = monitor.check_all_products()

            if changes:
                # Format and display notification
                notification = monitor.format_notification(changes)
                print(notification)

                # TODO: Send via email/Slack
                # import requests
                # requests.post(SLACK_WEBHOOK, json={'text': notification})

                # Mark changes as notified
                monitor.db.mark_all_notified()

            # Show stats
            stats = monitor.get_stats()
            logger.info(f"📊 Stats: {stats['tracked_products']} products tracked, "
                       f"{stats['total_snapshots']} snapshots, "
                       f"{stats['total_changes']} total changes")

        except Exception as e:
            logger.error(f"Monitoring error: {e}", exc_info=True)

        # Wait for next check
        logger.info(f"⏰ Next check in {interval_hours} hours...")
        time.sleep(interval_hours * 60 * 60)


if __name__ == "__main__":
    # Run standalone
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Run with custom interval (e.g., 1 hour for testing)
    run_monitoring_loop(interval_hours=1)
