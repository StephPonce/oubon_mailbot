"""Automated refund processing with safety parameters."""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import re


class RefundProcessor:
    """Process refund requests with configurable safety parameters."""

    def __init__(
        self,
        max_auto_refund_amount: float = 100.00,  # Max $100 auto-refunds
        auto_refund_days_limit: int = 30,        # Only auto-refund within 30 days
        require_reason_keywords: bool = True,     # Must have valid reason
        valid_reasons: Optional[list] = None,
    ):
        self.max_auto_refund_amount = max_auto_refund_amount
        self.auto_refund_days_limit = auto_refund_days_limit
        self.require_reason_keywords = require_reason_keywords
        self.valid_reasons = valid_reasons or [
            "damaged", "broken", "defective", "wrong item", "not as described",
            "missing parts", "quality issue", "not working", "arrived broken",
        ]

    def should_auto_refund(
        self,
        order_info: Dict[str, Any],
        message_body: str,
    ) -> Dict[str, Any]:
        """
        Determine if order qualifies for automatic refund.

        Args:
            order_info: Order data from Shopify
            message_body: Customer's email message

        Returns:
            {
                "eligible": bool,
                "reason": str,
                "action": "auto_refund" | "manual_review" | "reject",
                "refund_amount": float,
            }
        """
        result = {
            "eligible": False,
            "reason": "",
            "action": "manual_review",
            "refund_amount": 0.0,
        }

        # Check if order exists
        if not order_info:
            result["reason"] = "Order not found"
            return result

        # Get order details
        order_total = float(order_info.get("total_price", 0))
        order_date_str = order_info.get("created_at", "")

        try:
            order_date = datetime.fromisoformat(order_date_str.replace("Z", "+00:00"))
            days_since_order = (datetime.now(order_date.tzinfo) - order_date).days
        except (ValueError, AttributeError):
            result["reason"] = "Invalid order date"
            return result

        # Check 1: Order amount within auto-refund limit
        if order_total > self.max_auto_refund_amount:
            result["reason"] = f"Order total ${order_total:.2f} exceeds auto-refund limit ${self.max_auto_refund_amount:.2f}"
            result["action"] = "manual_review"
            return result

        # Check 2: Order within time limit
        if days_since_order > self.auto_refund_days_limit:
            result["reason"] = f"Order is {days_since_order} days old (limit: {self.auto_refund_days_limit} days)"
            result["action"] = "manual_review"
            return result

        # Check 3: Valid refund reason in message
        message_lower = message_body.lower()
        reason_found = None
        if self.require_reason_keywords:
            for reason in self.valid_reasons:
                if reason.lower() in message_lower:
                    reason_found = reason
                    break

            if not reason_found:
                result["reason"] = "No valid refund reason detected. Manual review required."
                result["action"] = "manual_review"
                return result

        # All checks passed - eligible for auto refund
        result["eligible"] = True
        result["action"] = "auto_refund"
        result["refund_amount"] = order_total
        result["reason"] = f"Auto-refund approved: {reason_found or 'customer request'}"

        return result

    def extract_order_id_from_message(self, subject: str, body: str) -> Optional[str]:
        """Extract order number from email subject/body."""
        text = f"{subject}\n{body}"

        # Pattern 1: Oubon order format (OU12345)
        m = re.search(r"\bOU\d{5,}\b", text, flags=re.I)
        if m:
            return m.group(0).upper()

        # Pattern 2: Order #12345
        m = re.search(r"\border\s*#\s*(\d{5,})\b", text, flags=re.I)
        if m:
            return m.group(1)

        # Pattern 3: #12345 in Shopify format
        m = re.search(r"#(\d{4,})\b", text)
        if m:
            return f"#{m.group(1)}"

        return None

    def generate_refund_response(
        self,
        customer_name: str,
        order_id: str,
        refund_decision: Dict[str, Any],
    ) -> str:
        """Generate email response based on refund decision."""
        if refund_decision["action"] == "auto_refund":
            return f"""<p>Hi {customer_name},</p>

<p>We're sorry to hear about the issue with your order #{order_id}.</p>

<p><strong>✅ Refund Approved</strong><br>
We've processed a full refund of <strong>${refund_decision['refund_amount']:.2f}</strong> to your original payment method.
You should see it within 5-7 business days.</p>

<p>If you have any other questions, please don't hesitate to reach out.</p>

<p>— Oubon Shop Support</p>"""

        elif refund_decision["action"] == "manual_review":
            return f"""<p>Hi {customer_name},</p>

<p>Thank you for contacting us about order #{order_id}.</p>

<p>We take your concern seriously. Our support team is reviewing your request
and will respond within 24 hours with a resolution.</p>

<p><strong>Reason:</strong> {refund_decision['reason']}</p>

<p>— Oubon Shop Support</p>"""

        else:  # reject
            return f"""<p>Hi {customer_name},</p>

<p>Thank you for contacting us about order #{order_id}.</p>

<p>Based on our review, we're unable to process an automatic refund at this time.
{refund_decision['reason']}</p>

<p>If you believe this is an error, please reply with additional details
and we'll be happy to take another look.</p>

<p>— Oubon Shop Support</p>"""
