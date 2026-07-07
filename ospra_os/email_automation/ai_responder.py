"""
AI Email Response Generator for Ospra Intelligence
v2.0 - Uses Model Router for Cost-Efficient Responses

Changes from v1:
- Uses model router (Groq Llama 8B for speed)
- Rule-based classification (no AI needed)
- Template-based structure with AI fill-in
- Temperature 0.3 for consistency
- Fallback responses if AI fails
"""

import os
import re
from typing import Dict, Optional
from datetime import datetime, time
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EmailCategory(Enum):
    ORDER_STATUS = "order_status"
    SHIPPING_TRACKING = "shipping_tracking"
    REFUND_REQUEST = "refund_request"
    RETURN_REQUEST = "return_request"
    PRODUCT_QUESTION = "product_question"
    COMPLAINT = "complaint"
    GENERAL_INQUIRY = "general_inquiry"
    DO_NOT_REPLY = "do_not_reply"
    THANK_YOU = "thank_you"


@dataclass
class EmailContext:
    email_id: str
    from_address: str
    from_name: str
    subject: str
    body: str
    received_at: datetime
    category: EmailCategory
    sentiment: str
    urgency: str
    order_number: Optional[str] = None
    order_status: Optional[str] = None
    store_name: str = "Oubon Shop"


class AIEmailResponder:
    """
    AI-powered email responder using model router for cost efficiency.
    
    Uses:
    - Rule-based classification (FREE)
    - Groq Llama 8B for responses (CHEAP + FAST)
    - Fallback templates if AI fails
    """
    
    OPERATING_HOURS_START = time(7, 0)
    OPERATING_HOURS_END = time(21, 0)
    
    DO_NOT_REPLY_PATTERNS = [
        "noreply@", "no-reply@", "donotreply@", "notifications@",
        "mailer-daemon@", "postmaster@", "newsletter@", "marketing@",
        "promo@", "info@shopify", "support@aliexpress", "service@paypal",
        "notification@", "alerts@", "updates@", "news@", "digest@"
    ]
    
    AUTO_IGNORE_SUBJECTS = [
        "confirmation code", "verify your email", "password reset",
        "order confirmation", "shipping notification", "your receipt",
        "automated message", "this is an automated", "do not reply",
        "invoice #", "payment received", "subscription", "newsletter"
    ]
    
    def __init__(self):
        self._router = None
    
    @property
    def router(self):
        """Lazy load router to avoid circular imports."""
        if self._router is None:
            try:
                from ospra_os.ai.model_router import get_model_router
                self._router = get_model_router()
            except Exception as e:
                logger.warning(f"Could not load model router: {e}")
        return self._router
    
    def is_operating_hours(self) -> bool:
        """Check if within business hours (timezone-aware, weekday/weekend).

        T109: this used naive ``datetime.now().time()``. On a UTC server (Render)
        that evaluated the 7am-9pm window in UTC — 4-5 hours off from the store's
        real timezone — so customers received full AI replies in the middle of
        the night and quiet-hours acknowledgements during business hours.
        Delegate to the single correct, pytz-based ``BusinessHours`` (defaults to
        America/New_York, weekend-aware). Override with OSPRA_BUSINESS_TIMEZONE.
        """
        if getattr(self, "_business_hours", None) is None:
            import os
            from ospra_os.email_automation.business_hours import BusinessHours
            self._business_hours = BusinessHours(
                timezone=os.getenv("OSPRA_BUSINESS_TIMEZONE", "America/New_York")
            )
        return self._business_hours.is_operating_hours()
    
    def should_auto_ignore(self, from_address: str, subject: str) -> bool:
        """Check if email should be auto-ignored (no reply needed)."""
        from_lower = from_address.lower()
        subject_lower = subject.lower()
        
        # Check sender patterns
        for pattern in self.DO_NOT_REPLY_PATTERNS:
            if pattern in from_lower:
                return True
        
        # Check subject patterns
        for pattern in self.AUTO_IGNORE_SUBJECTS:
            if pattern in subject_lower:
                return True
        
        return False
    
    def classify_email(self, subject: str, body: str) -> Dict:
        """
        Rule-based email classification - NO AI NEEDED!
        
        Returns:
            Dict with category, sentiment, urgency, order_number
        """
        text_lower = (subject + " " + body).lower()
        
        # Extract order number
        order_match = re.search(r'#?(\d{4,})', subject + " " + body)
        order_number = order_match.group(1) if order_match else None
        
        # COMPLAINTS - Check first (highest priority)
        complaint_words = [
            "complaint", "disappointed", "terrible", "worst", "horrible",
            "scam", "fraud", "sue", "lawyer", "bbb", "attorney general",
            "never again", "unacceptable", "disgusted", "furious", "livid"
        ]
        if any(w in text_lower for w in complaint_words):
            return {
                "category": EmailCategory.COMPLAINT,
                "sentiment": "very_negative",
                "urgency": "critical",
                "order_number": order_number
            }
        
        # REFUND REQUESTS
        refund_words = [
            "refund", "money back", "cancel order", "cancelled", "canceled",
            "charge back", "chargeback", "want my money", "full refund",
            "partial refund", "credit back"
        ]
        if any(w in text_lower for w in refund_words):
            return {
                "category": EmailCategory.REFUND_REQUEST,
                "sentiment": "negative",
                "urgency": "high",
                "order_number": order_number
            }
        
        # RETURN REQUESTS
        return_words = [
            "return", "exchange", "wrong item", "damaged", "broken",
            "defective", "doesn't work", "doesnt work", "send back",
            "rma", "not what i ordered", "incorrect item"
        ]
        if any(w in text_lower for w in return_words):
            return {
                "category": EmailCategory.RETURN_REQUEST,
                "sentiment": "negative",
                "urgency": "high",
                "order_number": order_number
            }
        
        # ORDER STATUS
        order_words = [
            "where is my order", "order status", "when will", "haven't received",
            "havent received", "not received", "still waiting", "how long",
            "when does", "when do i get", "where's my", "wheres my",
            "order update", "any update", "status of my order"
        ]
        if any(w in text_lower for w in order_words):
            return {
                "category": EmailCategory.ORDER_STATUS,
                "sentiment": "concerned",
                "urgency": "high",
                "order_number": order_number
            }
        
        # SHIPPING/TRACKING
        shipping_words = [
            "tracking", "track my", "shipping status", "delivery status",
            "shipment", "shipped yet", "tracking number", "where is package",
            "delivery date", "estimated delivery", "usps", "fedex", "ups"
        ]
        if any(w in text_lower for w in shipping_words):
            return {
                "category": EmailCategory.SHIPPING_TRACKING,
                "sentiment": "neutral",
                "urgency": "medium",
                "order_number": order_number
            }
        
        # THANK YOU / POSITIVE
        positive_words = [
            "thank", "thanks", "appreciate", "love it", "great product",
            "awesome", "perfect", "happy with", "excellent", "amazing",
            "wonderful", "fantastic", "love the"
        ]
        if any(w in text_lower for w in positive_words):
            return {
                "category": EmailCategory.THANK_YOU,
                "sentiment": "positive",
                "urgency": "low",
                "order_number": None
            }
        
        # PRODUCT QUESTIONS
        question_words = [
            "does this", "is this", "can i", "how does", "compatible",
            "size", "dimensions", "color", "specs", "specification",
            "what is", "how do i", "will this", "does it"
        ]
        if any(w in text_lower for w in question_words):
            return {
                "category": EmailCategory.PRODUCT_QUESTION,
                "sentiment": "neutral",
                "urgency": "medium",
                "order_number": None
            }
        
        # DEFAULT
        return {
            "category": EmailCategory.GENERAL_INQUIRY,
            "sentiment": "neutral",
            "urgency": "medium",
            "order_number": order_number
        }
    
    async def generate_response(self, context: EmailContext, response_type: str = "full") -> str:
        """
        Generate email response using model router.
        
        Uses Groq Llama 8B for speed and cost efficiency.
        Falls back to templates if AI fails.
        """
        # Try AI generation first
        try:
            if self.router:
                from ospra_os.ai.model_router import ai_email_response

                response = await ai_email_response(
                    customer_name=context.from_name or "Valued Customer",
                    category=context.category.value,
                    urgency=context.urgency,
                    subject=context.subject,
                    body=context.body[:500],
                    order_number=context.order_number,
                    response_type=response_type,
                    brand_name=context.store_name,
                )
                
                if response and len(response) > 20:
                    return response
                    
        except Exception as e:
            logger.warning(f"AI response generation failed: {e}")
        
        # Fallback to templates
        return self._get_template_response(context, response_type)
    
    def _get_template_response(self, context: EmailContext, response_type: str) -> str:
        """Get template-based fallback response."""
        name = context.from_name or "there"
        order_ref = f" (Order #{context.order_number})" if context.order_number else ""
        
        if response_type == "acknowledgment":
            return f"""Hi {name},

Thank you for contacting {context.store_name}! We've received your message{order_ref} and will respond during our business hours (7 AM - 9 PM EST).

If this is urgent, please reply with "URGENT" in the subject line.

Best regards,
{context.store_name} Support"""
        
        templates = {
            EmailCategory.ORDER_STATUS: f"""Hi {name},

Thank you for reaching out about your order{order_ref}!

I'd be happy to check on the status for you. Could you please confirm your order number so I can provide you with the most accurate update?

Best regards,
{context.store_name} Support""",

            EmailCategory.SHIPPING_TRACKING: f"""Hi {name},

I'd be glad to help you track your order{order_ref}!

If your order has shipped, you should have received a tracking email. If you haven't, please share your order number and I'll get that information for you right away.

Best regards,
{context.store_name} Support""",

            EmailCategory.REFUND_REQUEST: f"""Hi {name},

I understand you'd like to discuss a refund{order_ref}, and I want to help resolve this for you.

To process your request, please reply with:
• Your order number (if not already provided)
• Reason for the refund request

We'll get back to you within 24 hours.

Best regards,
{context.store_name} Support""",

            EmailCategory.RETURN_REQUEST: f"""Hi {name},

I'm sorry to hear there's an issue with your order{order_ref}.

To start your return, please reply with:
• Photos of the item (if damaged/defective)
• Your order number
• Description of the issue

We'll process your return request promptly.

Best regards,
{context.store_name} Support""",

            EmailCategory.COMPLAINT: f"""Hi {name},

I sincerely apologize for your experience. We take customer satisfaction very seriously, and I want to make this right.

Could you please share more details about what happened? I'll personally ensure your concern is addressed and resolved.

Best regards,
{context.store_name} Support""",

            EmailCategory.THANK_YOU: f"""Hi {name},

Thank you so much for your kind words! It means a lot to us.

We're thrilled you're happy with your purchase. If you ever need anything, don't hesitate to reach out!

Best regards,
{context.store_name} Support""",

            EmailCategory.PRODUCT_QUESTION: f"""Hi {name},

Thank you for your question! I'd be happy to help.

Could you please let me know which specific product you're asking about? I'll get you the information you need right away.

Best regards,
{context.store_name} Support""",
        }
        
        return templates.get(
            context.category,
            f"""Hi {name},

Thank you for contacting {context.store_name}! How can I help you today?

Please share any details that would help me assist you better.

Best regards,
{context.store_name} Support"""
        )


class EmailAutomationAI:
    """Main integration class for email automation."""
    
    def __init__(self):
        self.responder = AIEmailResponder()
    
    async def process_email(
        self,
        email_id: str,
        from_address: str,
        from_name: str,
        subject: str,
        body: str,
        received_at: datetime
    ) -> Dict:
        """
        Process incoming email and generate appropriate response.
        
        Flow:
        1. Check auto-ignore (rule-based, FREE)
        2. Classify email (rule-based, FREE)
        3. Generate response (AI via router, CHEAP)
        """
        # Step 1: Auto-ignore check
        if self.responder.should_auto_ignore(from_address, subject):
            return {
                "should_respond": False,
                "reason": "auto_ignore",
                "category": "do_not_reply"
            }
        
        # Step 2: Classification (rule-based)
        classification = self.responder.classify_email(subject, body)
        
        # Step 3: Build context
        context = EmailContext(
            email_id=email_id,
            from_address=from_address,
            from_name=from_name or from_address.split("@")[0].title(),
            subject=subject,
            body=body,
            received_at=received_at,
            category=classification["category"],
            sentiment=classification["sentiment"],
            urgency=classification["urgency"],
            order_number=classification.get("order_number")
        )
        
        # Step 4: Determine response type
        response_type = "full" if self.responder.is_operating_hours() else "acknowledgment"
        
        # Step 5: Generate response
        response_text = await self.responder.generate_response(context, response_type)
        
        return {
            "should_respond": True,
            "response_type": response_type,
            "response_text": response_text,
            "category": classification["category"].value,
            "sentiment": classification["sentiment"],
            "urgency": classification["urgency"],
            "order_number": classification.get("order_number")
        }


# ============================================================================
# TEST SUITE
# ============================================================================

async def test():
    """Comprehensive test of email automation."""
    ai = EmailAutomationAI()
    
    tests = [
        {
            "name": "Order Status Inquiry",
            "from": "john@gmail.com",
            "from_name": "John",
            "subject": "Where is my order #12345?",
            "body": "I ordered LED lights last week and still havent received them. Can you help?"
        },
        {
            "name": "Refund Request",
            "from": "jane@outlook.com",
            "from_name": "Jane Smith",
            "subject": "I want a refund",
            "body": "The product I received is not what I expected. I want my money back please."
        },
        {
            "name": "Angry Complaint",
            "from": "karen@gmail.com",
            "from_name": "Karen",
            "subject": "This is TERRIBLE",
            "body": "I am so disappointed with your service. This is the worst experience ever! I'm contacting BBB!"
        },
        {
            "name": "Auto-Ignore (noreply)",
            "from": "noreply@shopify.com",
            "from_name": "Shopify",
            "subject": "Order Confirmation #67890",
            "body": "Thank you for your order!"
        },
        {
            "name": "Tracking Request",
            "from": "mike@yahoo.com",
            "from_name": "Mike",
            "subject": "Tracking number please",
            "body": "Can you send me the tracking number for order 55555? I need to know when it arrives."
        },
        {
            "name": "Thank You Email",
            "from": "happy@gmail.com",
            "from_name": "Happy Customer",
            "subject": "Thank you!",
            "body": "Just wanted to say thanks, I love the product! It works perfectly."
        },
        {
            "name": "Product Question",
            "from": "curious@gmail.com",
            "from_name": "Curious Buyer",
            "subject": "Question about LED strip",
            "body": "Does this LED strip work with Alexa? What are the dimensions?"
        }
    ]
    
    print("\n" + "="*70)
    print("[TEST] AI EMAIL RESPONDER v2.0 - COMPREHENSIVE TEST")
    print("="*70)
    
    for i, test in enumerate(tests, 1):
        print(f"\n{''*70}")
        print(f"TEST {i}: {test['name']}")
        print(f"{''*70}")
        print(f"From: {test['from_name']} <{test['from']}>")
        print(f"Subject: {test['subject']}")
        
        result = await ai.process_email(
            f"test_{i}",
            test["from"],
            test["from_name"],
            test["subject"],
            test["body"],
            datetime.now()
        )
        
        if result.get('should_respond'):
            print(f"\n[SUCCESS] Category: {result['category']}")
            print(f"[FAST] Urgency: {result['urgency']}")
            print(f" Sentiment: {result['sentiment']}")
            print(f"[EMAIL] Type: {result['response_type']}")
            if result.get('order_number'):
                print(f" Order: #{result['order_number']}")
            print(f"\n[NOTE] Response:\n{result['response_text']}")
        else:
            print(f"\n⏭  AUTO-IGNORED: {result.get('reason', 'N/A')}")
    
    print("\n" + "="*70)
    print("[SUCCESS] ALL TESTS COMPLETE")
    print("="*70 + "\n")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test())
