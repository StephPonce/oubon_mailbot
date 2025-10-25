"""
Oubon Shop - Company Policies and Guidelines
This file is used by AI agents to understand company policies and provide accurate customer support.
"""

COMPANY_INFO = {
    "name": "Oubon Shop",
    "website": "oubonshop.com",
    "support_email": "hello@oubonshop.com",
    "operating_hours": {
        "weekday": "Monday-Friday, 7 AM - 9 PM EST",
        "weekend": "Saturday-Sunday, 10 AM - 7 PM EST",
        "timezone": "America/New_York (EST/EDT)"
    }
}

REFUND_POLICY = """
## Refund Policy

### Automatic Refunds (Processed Immediately)
We offer automatic refunds for orders that meet ALL of the following criteria:
- Order total is $100 or less
- Purchase was made within the last 15 days
- Item has a valid quality issue (damaged, defective, wrong item, not as described)
- Customer confirms they will ship the item back

### Manual Review Required
Orders requiring manual review (24-48 hour response time):
- Orders over $100
- Orders older than 15 days
- No quality issue cited (buyer's remorse, changed mind)
- Customer has not confirmed they will ship item back

### How to Request a Refund
1. Email us at hello@oubonshop.com with your order number
2. Describe the issue with the product
3. Confirm that you will ship the item back to us
4. We'll process eligible refunds within 24 hours
5. Refunds appear in 5-7 business days on original payment method

### Return Shipping
- Customer is responsible for return shipping costs
- We recommend using a tracked shipping method
- Keep your tracking number for reference
"""

RETURN_POLICY = """
## Return Policy

### Return Window
- Returns accepted within 30 days of delivery
- Item must be in original condition with tags attached
- Original packaging preferred but not required

### Non-Returnable Items
- Final sale items (marked as such on product page)
- Personalized or custom-made items
- Hygiene products that have been opened

### Return Process
1. Email hello@oubonshop.com with order number
2. We'll provide return shipping instructions
3. Ship item back with tracking
4. Refund processed within 5 business days of receiving return
"""

SHIPPING_POLICY = """
## Shipping Policy

### Domestic Shipping (United States)
- Standard Shipping: 5-7 business days
- Express Shipping: 2-3 business days
- Free shipping on orders over $50

### International Shipping
- Available to select countries
- 10-21 business days depending on destination
- Customer responsible for customs fees

### Tracking
- Tracking numbers sent via email within 24 hours of shipment
- Track packages at: oubonshop.com/track or via carrier website

### Lost or Damaged Packages
- Contact us immediately at hello@oubonshop.com
- Include order number and photo of damage (if applicable)
- We'll work with carrier to resolve or send replacement
"""

ORDER_STATUS_INFO = """
## Order Status Guide

### Order Confirmed
- Payment received and order being prepared
- Usually ships within 1-2 business days

### Shipped
- Package is with carrier and on its way
- Tracking number available

### Out for Delivery
- Package will arrive today

### Delivered
- Package has been delivered according to carrier
- If you haven't received it, check with neighbors or building management
- Contact us if still missing after 24 hours
"""

CUSTOMER_SERVICE_APPROACH = """
## Customer Service Guidelines

### Tone and Voice
- Warm, professional, and modern
- Empathetic and solution-focused
- Concise but helpful (2-3 paragraphs max)
- Never overly formal or robotic

### Response Priorities
1. Acknowledge their concern/frustration
2. Provide specific next steps or solutions
3. Ask for any missing information needed
4. Set clear expectations for timing

### Quality Issues Response
- Apologize for the inconvenience
- Offer immediate refund for eligible orders
- Ask for photos if details are unclear
- Provide replacement option if available

### Tracking Inquiries
- Look up order in Shopify system
- Provide current tracking status
- Explain typical delivery timeframes
- Offer solutions if delayed

### General Inquiries
- Answer question directly and concisely
- Provide relevant policy information
- Link to help center if applicable
- Offer to help with anything else
"""

COMMON_SCENARIOS = {
    "damaged_product": {
        "response_approach": "Apologize, verify order is within 15 days and under $100, process automatic refund if eligible, otherwise escalate to manual review",
        "key_info_needed": ["order_number", "description_of_damage", "confirmation_will_ship_back"],
    },
    "where_is_my_order": {
        "response_approach": "Look up order in Shopify, provide current tracking status and expected delivery date",
        "key_info_needed": ["order_number", "email_used_at_checkout"],
    },
    "want_to_return": {
        "response_approach": "Confirm return is within 30 days, explain return process, provide return instructions",
        "key_info_needed": ["order_number", "reason_for_return"],
    },
    "wrong_item_received": {
        "response_approach": "Apologize, process automatic refund if eligible, offer correct item shipment if in stock",
        "key_info_needed": ["order_number", "item_received", "item_expected"],
    },
    "package_stolen": {
        "response_approach": "Express concern, file claim with carrier, offer replacement or refund",
        "key_info_needed": ["order_number", "tracking_number", "delivery_photo_if_available"],
    },
}

FAQ = {
    "How long does shipping take?": "Standard shipping takes 5-7 business days. Express shipping is 2-3 business days. You'll receive a tracking number within 24 hours of your order shipping.",

    "Do you ship internationally?": "Yes, we ship to select countries. International shipping takes 10-21 business days. Note that customers are responsible for any customs fees.",

    "What's your refund policy?": "We offer refunds within 15 days for quality issues (damaged, defective, wrong item). Orders $100 or less are processed automatically. Just email us with your order number and confirm you'll ship the item back.",

    "How do I track my order?": "We'll email you a tracking number within 24 hours of shipping. You can track at oubonshop.com/track or directly on the carrier's website.",

    "Can I change my shipping address?": "If your order hasn't shipped yet, we can update the address. Contact us immediately with your order number and new address.",

    "Do you offer exchanges?": "We don't offer direct exchanges, but you can return the original item for a refund and place a new order for the item you'd like.",
}


def get_policy_context() -> str:
    """
    Get formatted policy context for AI to reference.
    Returns a string with all relevant policies.
    """
    context = f"""
# Oubon Shop Customer Support Policies

## Company Information
{COMPANY_INFO['name']}
Support: {COMPANY_INFO['support_email']}
Operating Hours:
- Weekdays: {COMPANY_INFO['operating_hours']['weekday']}
- Weekends: {COMPANY_INFO['operating_hours']['weekend']}

{REFUND_POLICY}

{RETURN_POLICY}

{SHIPPING_POLICY}

{ORDER_STATUS_INFO}

{CUSTOMER_SERVICE_APPROACH}
"""
    return context


def get_scenario_guidance(scenario_type: str) -> dict:
    """Get specific guidance for common scenarios."""
    return COMMON_SCENARIOS.get(scenario_type, {})


def get_faq_answer(question: str) -> str:
    """Get answer to common questions."""
    # Simple keyword matching for FAQs
    question_lower = question.lower()
    for faq_q, faq_a in FAQ.items():
        if any(word in question_lower for word in faq_q.lower().split()):
            return faq_a
    return ""
