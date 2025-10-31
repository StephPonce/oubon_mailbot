"""Enhanced Shopify integration for order lookup, tracking, and refunds."""
from typing import Optional, Dict, Any
import requests
from datetime import datetime


class ShopifyClient:
    """Enhanced Shopify Admin API client."""

    def __init__(self, store_domain: str, api_token: str, api_version: str = "2025-01"):
        """
        Initialize Shopify client.

        Args:
            store_domain: e.g., "oubonshop.myshopify.com"
            api_token: Shopify Admin API access token
            api_version: API version (default: 2025-01)
        """
        self.store_domain = store_domain
        self.api_token = api_token
        self.api_version = api_version
        self.base_url = f"https://{store_domain}/admin/api/{api_version}"
        self.headers = {
            "X-Shopify-Access-Token": api_token,
            "Content-Type": "application/json",
        }

    def lookup_order(self, order_identifier: str) -> Optional[Dict[str, Any]]:
        """
        Look up order by order number or name.

        Args:
            order_identifier: Order number (e.g., "#1001" or "1001")

        Returns:
            Order details dict or None if not found
        """
        # Clean order identifier
        order_name = order_identifier.strip()
        if not order_name.startswith("#"):
            order_name = f"#{order_name}"

        try:
            url = f"{self.base_url}/orders.json?name={order_name}&status=any"
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()

            data = response.json()
            orders = data.get("orders", [])

            if not orders:
                return None

            return orders[0]  # Return first matching order

        except Exception as e:
            print(f"Error looking up order {order_identifier}: {e}")
            return None

    def get_order_status(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract comprehensive order status information.

        Returns:
            {
                "order_id": str,
                "order_number": int,
                "status": str,  # "fulfilled", "unfulfilled", "partially_fulfilled"
                "financial_status": str,  # "paid", "pending", "refunded"
                "fulfillment_status": str,
                "tracking_info": list,
                "created_at": str,
                "total_price": float,
                "currency": str,
                "customer_email": str,
            }
        """
        # Extract tracking information from fulfillments
        tracking_info = []
        fulfillments = order_data.get("fulfillments", [])
        for fulfillment in fulfillments:
            tracking_company = fulfillment.get("tracking_company", "")
            tracking_number = fulfillment.get("tracking_number", "")
            tracking_url = fulfillment.get("tracking_url", "")
            tracking_urls = fulfillment.get("tracking_urls", [])

            if tracking_number:
                tracking_info.append({
                    "carrier": tracking_company or "Unknown",
                    "tracking_number": tracking_number,
                    "tracking_url": tracking_url or (tracking_urls[0] if tracking_urls else ""),
                    "status": fulfillment.get("shipment_status", ""),
                })

        return {
            "order_id": order_data.get("name", ""),  # e.g., "#1001"
            "order_number": order_data.get("order_number", 0),
            "status": order_data.get("fulfillment_status") or "unfulfilled",
            "financial_status": order_data.get("financial_status", ""),
            "fulfillment_status": order_data.get("fulfillment_status", ""),
            "tracking_info": tracking_info,
            "created_at": order_data.get("created_at", ""),
            "updated_at": order_data.get("updated_at", ""),
            "total_price": float(order_data.get("total_price", 0)),
            "currency": order_data.get("currency", "USD"),
            "customer_email": order_data.get("email", ""),
            "line_items": order_data.get("line_items", []),
        }

    def process_refund(
        self,
        order_id: int,
        amount: float,
        reason: str = "customer_request",
        notify_customer: bool = True,
    ) -> Dict[str, Any]:
        """
        Process a refund for an order.

        Args:
            order_id: Shopify order ID (not order number)
            amount: Refund amount
            reason: Refund reason
            notify_customer: Send email notification to customer

        Returns:
            {"success": bool, "refund_id": int, "error": str}
        """
        try:
            url = f"{self.base_url}/orders/{order_id}/refunds.json"

            # Calculate refund transactions
            refund_data = {
                "refund": {
                    "currency": "USD",
                    "notify": notify_customer,
                    "note": reason,
                    "transactions": [
                        {
                            "kind": "refund",
                            "amount": amount,
                        }
                    ],
                }
            }

            response = requests.post(url, headers=self.headers, json=refund_data, timeout=10)
            response.raise_for_status()

            refund = response.json().get("refund", {})
            return {
                "success": True,
                "refund_id": refund.get("id"),
                "error": None,
            }

        except Exception as e:
            return {
                "success": False,
                "refund_id": None,
                "error": str(e),
            }

    def format_tracking_response(self, status: Dict[str, Any], customer_name: str) -> str:
        """Generate HTML email response with tracking information."""
        order_id = status["order_id"]
        tracking_info = status["tracking_info"]

        if not tracking_info:
            return f"""<p>Hi {customer_name},</p>

<p>Your order <strong>{order_id}</strong> is currently being prepared for shipment.</p>

<p><strong>Status:</strong> {status['status'].replace('_', ' ').title()}<br>
<strong>Order Date:</strong> {self._format_date(status['created_at'])}</p>

<p>We'll send you tracking information as soon as your order ships!</p>

<p>— Oubon Shop Support</p>"""

        # Has tracking info
        tracking_html = ""
        for i, track in enumerate(tracking_info, 1):
            carrier = track["carrier"]
            number = track["tracking_number"]
            url = track["tracking_url"]
            track_status = track["status"]

            tracking_html += f"""
<p><strong>Shipment {i}:</strong><br>
Carrier: {carrier}<br>
Tracking #: {number}"""

            if url:
                tracking_html += f'<br><a href="{url}">Track Package</a>'

            if track_status:
                tracking_html += f"<br>Status: {track_status.replace('_', ' ').title()}"

            tracking_html += "</p>"

        return f"""<p>Hi {customer_name},</p>

<p>Here's the latest on your order <strong>{order_id}</strong>:</p>

{tracking_html}

<p><strong>Order Date:</strong> {self._format_date(status['created_at'])}<br>
<strong>Order Total:</strong> ${status['total_price']:.2f}</p>

<p>If you have any questions, just reply to this email!</p>

<p>— Oubon Shop Support</p>"""

    def _format_date(self, date_str: str) -> str:
        """Format ISO date to readable format."""
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.strftime("%B %d, %Y")
        except (ValueError, AttributeError):
            return date_str
