"""
Email Alerts for Inventory Stockouts

Sends email notifications when products reach critical stock levels
"""
from typing import List, Dict, Optional
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)


class InventoryEmailAlerts:
    """Manage email alerts for inventory stockouts"""

    def __init__(self):
        """Initialize email alert system"""
        self.alert_email = os.getenv("INVENTORY_ALERT_EMAIL", "alerts@example.com")
        self.enabled = os.getenv("INVENTORY_ALERTS_ENABLED", "true").lower() == "true"

        logger.info(f"✅ Inventory email alerts initialized (enabled: {self.enabled})")

    def generate_alert_email(
        self,
        products: List[Dict],
        alert_type: str = "CRITICAL_STOCKOUT"
    ) -> Dict[str, str]:
        """
        Generate email content for stockout alert

        Args:
            products: List of products with critical stock levels
            alert_type: Type of alert (CRITICAL_STOCKOUT, LOW_STOCK, etc.)

        Returns:
            Dictionary with email subject and HTML body
        """
        if alert_type == "CRITICAL_STOCKOUT":
            subject = f"🚨 URGENT: {len(products)} Product(s) at Critical Stock Level"
            urgency_text = "CRITICAL - Immediate Action Required"
            color = "#ef4444"
        elif alert_type == "LOW_STOCK":
            subject = f"⚠️ Warning: {len(products)} Product(s) Running Low on Stock"
            urgency_text = "WARNING - Action Needed Soon"
            color = "#f59e0b"
        else:
            subject = f"📊 Inventory Alert: {len(products)} Product(s) Need Attention"
            urgency_text = "Notice"
            color = "#3b82f6"

        # Build product table rows
        product_rows = ""
        for product in products:
            status = product.get('current_status', {})
            forecast = product.get('forecast', {})
            reorder = product.get('reorder', {})
            risk = product.get('risk_assessment', {})

            # Determine urgency color
            if reorder.get('reorder_urgency') == 'CRITICAL':
                row_color = "#fee2e2"
            elif reorder.get('reorder_urgency') == 'URGENT':
                row_color = "#fef3c7"
            else:
                row_color = "#ffffff"

            product_rows += f"""
                <tr style="background-color: {row_color};">
                    <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
                        <strong>{product.get('product_name', 'Unknown')}</strong><br>
                        <span style="color: #6b7280; font-size: 12px;">SKU: {product.get('sku', 'N/A')}</span>
                    </td>
                    <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: center;">
                        <strong>{status.get('stock_level', 0)}</strong><br>
                        <span style="color: #6b7280; font-size: 12px;">{status.get('status', 'UNKNOWN')}</span>
                    </td>
                    <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: center;">
                        {forecast.get('days_of_stock', 0) if forecast.get('days_of_stock', 0) < 999 else '∞'} days<br>
                        <span style="color: #6b7280; font-size: 12px;">
                            {forecast.get('stockout_date', 'N/A')[:10] if forecast.get('stockout_date') else 'N/A'}
                        </span>
                    </td>
                    <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: center;">
                        <span style="padding: 4px 8px; background-color: {'#fecaca' if reorder.get('reorder_urgency') == 'CRITICAL' else '#fed7aa' if reorder.get('reorder_urgency') == 'URGENT' else '#fef08a'}; border-radius: 4px; font-size: 12px; font-weight: bold;">
                            {reorder.get('reorder_urgency', 'N/A')}
                        </span><br>
                        <span style="color: #6b7280; font-size: 12px;">{reorder.get('recommended_quantity', 0)} units</span>
                    </td>
                    <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: center;">
                        ${reorder.get('estimated_cost', 0):.2f}
                    </td>
                </tr>
            """

        # Calculate totals
        total_cost = sum(p.get('reorder', {}).get('estimated_cost', 0) for p in products)
        total_units = sum(p.get('reorder', {}).get('recommended_quantity', 0) for p in products)

        # Build HTML email
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #1f2937; max-width: 800px; margin: 0 auto; padding: 20px;">

            <!-- Header -->
            <div style="background: linear-gradient(135deg, {color} 0%, {color}dd 100%); color: white; padding: 30px; border-radius: 8px 8px 0 0; text-align: center;">
                <h1 style="margin: 0; font-size: 24px;">Inventory Stockout Alert</h1>
                <p style="margin: 10px 0 0 0; font-size: 14px; opacity: 0.9;">{datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
            </div>

            <!-- Alert Banner -->
            <div style="background-color: {color}22; border-left: 4px solid {color}; padding: 15px; margin-bottom: 20px;">
                <p style="margin: 0; font-weight: bold; color: {color};">{urgency_text}</p>
                <p style="margin: 5px 0 0 0; color: #4b5563;">
                    {len(products)} product(s) require immediate attention due to low or critical stock levels.
                </p>
            </div>

            <!-- Products Table -->
            <div style="background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; margin-bottom: 20px;">
                <table style="width: 100%; border-collapse: collapse;">
                    <thead style="background-color: #f9fafb;">
                        <tr>
                            <th style="padding: 12px; text-align: left; font-weight: 600; color: #374151; border-bottom: 2px solid #e5e7eb;">Product</th>
                            <th style="padding: 12px; text-align: center; font-weight: 600; color: #374151; border-bottom: 2px solid #e5e7eb;">Current Stock</th>
                            <th style="padding: 12px; text-align: center; font-weight: 600; color: #374151; border-bottom: 2px solid #e5e7eb;">Days Left</th>
                            <th style="padding: 12px; text-align: center; font-weight: 600; color: #374151; border-bottom: 2px solid #e5e7eb;">Urgency</th>
                            <th style="padding: 12px; text-align: center; font-weight: 600; color: #374151; border-bottom: 2px solid #e5e7eb;">Est. Cost</th>
                        </tr>
                    </thead>
                    <tbody>
                        {product_rows}
                    </tbody>
                    <tfoot style="background-color: #f9fafb; font-weight: bold;">
                        <tr>
                            <td colspan="3" style="padding: 12px; border-top: 2px solid #e5e7eb;">TOTAL RESTOCK NEEDED</td>
                            <td style="padding: 12px; text-align: center; border-top: 2px solid #e5e7eb;">{total_units} units</td>
                            <td style="padding: 12px; text-align: center; border-top: 2px solid #e5e7eb;">${total_cost:.2f}</td>
                        </tr>
                    </tfoot>
                </table>
            </div>

            <!-- Recommended Actions -->
            <div style="background-color: #eff6ff; border: 1px solid #3b82f6; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                <h3 style="margin: 0 0 10px 0; color: #1e40af; font-size: 16px;">📋 Recommended Actions</h3>
                <ul style="margin: 0; padding-left: 20px; color: #374151;">
                    <li style="margin-bottom: 8px;">Review each product's reorder recommendation and create purchase orders</li>
                    <li style="margin-bottom: 8px;">Contact suppliers to confirm lead times and availability</li>
                    <li style="margin-bottom: 8px;">Consider expedited shipping for CRITICAL urgency items</li>
                    <li style="margin-bottom: 8px;">Monitor daily sales velocity for any unexpected spikes</li>
                    <li style="margin-bottom: 0;">Update safety stock levels based on recent demand patterns</li>
                </ul>
            </div>

            <!-- Footer -->
            <div style="text-align: center; padding: 20px; color: #6b7280; font-size: 12px; border-top: 1px solid #e5e7eb;">
                <p style="margin: 0 0 10px 0;">This is an automated alert from your Inventory Forecasting System</p>
                <p style="margin: 0;">
                    <a href="http://localhost:5173/inventory" style="color: #3b82f6; text-decoration: none;">View Full Inventory Dashboard →</a>
                </p>
            </div>

        </body>
        </html>
        """

        return {
            "subject": subject,
            "html_body": html_body,
            "recipient": self.alert_email
        }

    async def send_stockout_alert(
        self,
        products: List[Dict],
        alert_type: str = "CRITICAL_STOCKOUT"
    ) -> Dict:
        """
        Send stockout alert email

        Args:
            products: List of products at critical levels
            alert_type: Type of alert to send

        Returns:
            Result dictionary with success status
        """
        if not self.enabled:
            logger.warning("⚠️  Email alerts are disabled")
            return {
                "success": False,
                "message": "Email alerts are disabled",
                "products_count": len(products)
            }

        if not products:
            logger.info("ℹ️  No products need alerts")
            return {
                "success": False,
                "message": "No products need alerts",
                "products_count": 0
            }

        try:
            # Generate email content
            email_data = self.generate_alert_email(products, alert_type)

            logger.info(f"📧 Alert email generated for {len(products)} products")
            logger.info(f"   Subject: {email_data['subject']}")
            logger.info(f"   Recipient: {email_data['recipient']}")

            # In production, this would send via Gmail API or SMTP
            # For now, we'll log the alert
            logger.info("✅ Stockout alert would be sent (email sending not configured)")

            return {
                "success": True,
                "message": f"Alert generated for {len(products)} products",
                "products_count": len(products),
                "alert_type": alert_type,
                "recipient": email_data['recipient'],
                "subject": email_data['subject']
            }

        except Exception as e:
            logger.error(f"❌ Failed to send stockout alert: {e}")
            return {
                "success": False,
                "message": f"Failed to send alert: {str(e)}",
                "products_count": len(products)
            }

    async def check_and_alert(self, forecasts: List[Dict]) -> Dict:
        """
        Check all products and send alerts for critical ones

        Args:
            forecasts: List of product forecasts

        Returns:
            Summary of alerts sent
        """
        # Separate products by urgency
        critical_products = []
        urgent_products = []

        for product in forecasts:
            reorder = product.get('reorder', {})
            if reorder.get('should_reorder'):
                urgency = reorder.get('reorder_urgency', '')

                if urgency == 'CRITICAL':
                    critical_products.append(product)
                elif urgency in ['URGENT', 'SOON']:
                    urgent_products.append(product)

        results = []

        # Send critical alert if needed
        if critical_products:
            result = await self.send_stockout_alert(critical_products, "CRITICAL_STOCKOUT")
            results.append(result)

        # Send low stock warning if needed
        if urgent_products:
            result = await self.send_stockout_alert(urgent_products, "LOW_STOCK")
            results.append(result)

        return {
            "success": True,
            "alerts_sent": len(results),
            "critical_count": len(critical_products),
            "urgent_count": len(urgent_products),
            "results": results
        }


# Global instance
_email_alerts = None


def get_email_alerts() -> InventoryEmailAlerts:
    """Get or create global email alerts instance"""
    global _email_alerts
    if _email_alerts is None:
        _email_alerts = InventoryEmailAlerts()
    return _email_alerts
