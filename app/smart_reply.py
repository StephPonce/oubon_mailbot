"""Intelligent auto-reply system with hybrid AI/template responses."""
from typing import Dict, Any, Optional
from datetime import datetime
from app.business_hours import BusinessHours
from app.shopify_client import ShopifyClient
from app.refund_processor import RefundProcessor
from app.ai_client import AIClient
from app.settings import Settings
import re


class SmartReplySystem:
    """
    Intelligent email auto-reply system that:
    - Uses AI during operating hours, templates during quiet hours
    - Handles order lookup and tracking automatically
    - Processes refunds within safety parameters
    - Personalizes responses based on email content
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.business_hours = BusinessHours(
            weekday_start=datetime.strptime("07:00", "%H:%M").time(),
            weekday_end=datetime.strptime("21:00", "%H:%M").time(),
            weekend_start=datetime.strptime("10:00", "%H:%M").time(),
            weekend_end=datetime.strptime("19:00", "%H:%M").time(),
            timezone="America/New_York",  # EST/EDT for Oubon
        )
        self.ai_client = AIClient(settings)

        # Initialize Shopify client if configured
        self.shopify = None
        if settings.SHOPIFY_STORE and settings.SHOPIFY_API_TOKEN:
            self.shopify = ShopifyClient(
                store_domain=settings.SHOPIFY_STORE,
                api_token=settings.SHOPIFY_API_TOKEN,
            )

        # Initialize refund processor with safety limits
        self.refund_processor = RefundProcessor(
            max_auto_refund_amount=100.00,  # Max $100 automatic refunds
            auto_refund_days_limit=30,       # Only within 30 days of purchase
            require_reason_keywords=True,
        )

    def generate_reply(
        self,
        subject: str,
        body: str,
        from_email: str,
        from_name: str,
        rule: Dict[str, Any],
        templates: Dict[str, Any],
    ) -> Optional[Dict[str, str]]:
        """
        Generate intelligent auto-reply based on business hours and email content.

        Returns:
            {
                "subject": str,
                "body": str,
                "metadata": dict  # For logging/tracking
            }
        """
        response_mode = self.business_hours.get_response_mode()
        label = rule.get("apply_label", "")

        # Extract customer first name
        customer_name = self._extract_first_name(from_name, from_email)

        metadata = {
            "response_mode": response_mode,
            "label": label,
            "used_shopify": False,
            "used_ai": False,
            "refund_attempted": False,
        }

        # Handle specific categories with special logic
        if label == "Tracking" or label == "Order Help":
            return self._handle_order_tracking(subject, body, customer_name, templates, metadata)

        elif label == "Return/Refund":
            return self._handle_refund_request(subject, body, customer_name, from_email, templates, metadata)

        elif label == "Support":
            return self._handle_quality_issue(subject, body, customer_name, templates, metadata)

        # For other categories, use hybrid AI/template approach
        if response_mode == "ai":
            # Use AI during business hours
            metadata["used_ai"] = True
            metadata["ai_provider"] = self.ai_client.get_provider_name()
            ai_body = self.ai_client.draft_reply(subject, body)
            return {
                "subject": f"Re: {subject}" if subject else "Thanks for your message",
                "body": ai_body,
                "metadata": metadata,
            }
        else:
            # Use template during quiet hours or if AI unavailable
            return self._use_template(rule, templates, customer_name, metadata)

    def _handle_order_tracking(
        self,
        subject: str,
        body: str,
        customer_name: str,
        templates: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle tracking/order status inquiries with Shopify lookup."""
        # Try to extract order ID
        order_id = self._extract_order_id(subject, body)

        if order_id and self.shopify:
            # Lookup order in Shopify
            order_data = self.shopify.lookup_order(order_id)

            if order_data:
                metadata["used_shopify"] = True
                order_status = self.shopify.get_order_status(order_data)

                # Generate tracking response with real data
                response_body = self.shopify.format_tracking_response(order_status, customer_name)

                return {
                    "subject": f"Tracking info for order {order_status['order_id']}",
                    "body": response_body,
                    "metadata": metadata,
                }

        # Fallback to template if no order ID or lookup failed
        template = templates.get("tracking_lookup", {})
        return {
            "subject": template.get("subject", "Re: Your order"),
            "body": template.get("body", "").replace("{{name}}", customer_name),
            "metadata": metadata,
        }

    def _handle_refund_request(
        self,
        subject: str,
        body: str,
        customer_name: str,
        customer_email: str,
        templates: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle refund requests with automatic processing for eligible orders."""
        order_id = self._extract_order_id(subject, body)

        if order_id and self.shopify:
            order_data = self.shopify.lookup_order(order_id)

            if order_data:
                metadata["used_shopify"] = True
                metadata["refund_attempted"] = True

                # Check if eligible for auto-refund
                refund_decision = self.refund_processor.should_auto_refund(order_data, body)

                # Generate response based on refund decision
                response_body = self.refund_processor.generate_refund_response(
                    customer_name,
                    order_id,
                    refund_decision,
                )

                # Actually process the refund if approved
                if refund_decision["action"] == "auto_refund":
                    refund_result = self.shopify.process_refund(
                        order_id=order_data["id"],
                        amount=refund_decision["refund_amount"],
                        reason=refund_decision["reason"],
                        notify_customer=False,  # We're sending our own email
                    )
                    metadata["refund_success"] = refund_result["success"]
                    metadata["refund_id"] = refund_result.get("refund_id")

                return {
                    "subject": f"Your refund request for order {order_id}",
                    "body": response_body,
                    "metadata": metadata,
                }

        # Fallback to template
        template = templates.get("refund_request", {})
        return {
            "subject": template.get("subject", "Your refund request").replace("{{order_id}}", order_id or ""),
            "body": template.get("body", "").replace("{{name}}", customer_name).replace("{{order_id}}", order_id or "your order"),
            "metadata": metadata,
        }

    def _handle_quality_issue(
        self,
        subject: str,
        body: str,
        customer_name: str,
        templates: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle quality issues (damaged, defective, wrong item)."""
        # Use AI during business hours for personalized empathy
        response_mode = self.business_hours.get_response_mode()

        if response_mode == "ai":
            metadata["used_ai"] = True
            metadata["ai_provider"] = self.ai_client.get_provider_name()
            ai_body = self.ai_client.draft_reply(subject, body)
            return {
                "subject": f"Re: {subject}" if subject else "We're here to help",
                "body": ai_body,
                "metadata": metadata,
            }

        # Use template during quiet hours
        template = templates.get("support_quality", {})
        return {
            "subject": template.get("subject", "We're here to help"),
            "body": template.get("body", "").replace("{{name}}", customer_name),
            "metadata": metadata,
        }

    def _use_template(
        self,
        rule: Dict[str, Any],
        templates: Dict[str, Any],
        customer_name: str,
        metadata: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Use template-based reply."""
        template_name = rule.get("auto_reply_template")

        if not template_name:
            return None

        # Use quiet hours template during off-hours
        response_mode = self.business_hours.get_response_mode()
        if response_mode == "template":
            template_name = "quiet_hours_auto"

        template = templates.get(template_name, {})

        if not template:
            return None

        return {
            "subject": template.get("subject", "Re: Your message"),
            "body": template.get("body", "").replace("{{name}}", customer_name),
            "metadata": metadata,
        }

    def _extract_order_id(self, subject: str, body: str) -> Optional[str]:
        """Extract order number from email."""
        text = f"{subject}\n{body}"

        # Pattern 1: #1234 format
        m = re.search(r"#(\d{4,})", text)
        if m:
            return f"#{m.group(1)}"

        # Pattern 2: Order #1234 or order number 1234
        m = re.search(r"\border\s*(?:#|number)?\s*(\d{4,})\b", text, flags=re.I)
        if m:
            return f"#{m.group(1)}"

        return None

    def _extract_first_name(self, from_name: str, from_email: str) -> str:
        """Extract customer's first name from email headers."""
        # Try from_name first
        if from_name:
            name = from_name.strip().strip('"').strip("'")
            if name:
                return name.split()[0]

        # Fallback to email username
        if from_email and "@" in from_email:
            username = from_email.split("@")[0]
            # Clean up common patterns like "john.doe" -> "John"
            return username.split(".")[0].capitalize()

        return "there"
