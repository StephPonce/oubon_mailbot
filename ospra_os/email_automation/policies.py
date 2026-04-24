"""
Customer-support company policies and guidelines
=================================================

The content here is fed into the email-AI system prompt (see
`ai/multi_provider_client.AIClient._get_relevant_policy`) so the LLM
can accurately quote refund rules, shipping windows, support email,
and tracking URLs when drafting customer replies.

Pass 4b SaaS refactor
---------------------
Previously everything in this file was hardcoded to Oubon Shop — the
company name, hello@oubonshop.com, oubonshop.com/track, EST timezone,
etc. That meant a second tenant would have gotten an AI draft that
signed as "Acme Support" but quoted Oubon's email and tracking URL in
the body.

Every policy is now a render function that accepts a brand context
(name / website / support_email / tracking_url / timezone / descriptor)
and returns the policy string with those values substituted in. Oubon's
values are the defaults, so the single-tenant production behavior is
unchanged when callers omit the kwargs.

Backward-compat shims (`REFUND_POLICY`, `RETURN_POLICY`, `FAQ`, etc.)
are preserved as module-level constants rendered with Oubon defaults.
Existing imports in downstream code keep working; new multi-tenant
callers should use the `render_*` functions instead.
"""

from __future__ import annotations

from typing import Dict

from ospra_os.tenancy.brand import (
    DEFAULT_BRAND_NAME,
    DEFAULT_SUPPORT_EMAIL,
    DEFAULT_TIMEZONE,
    DEFAULT_TRACKING_URL,
    DEFAULT_WEBSITE,
)


# ============================================================================
# COMPANY INFO
# ============================================================================

def render_company_info(
    brand_name: str = DEFAULT_BRAND_NAME,
    website: str = DEFAULT_WEBSITE,
    support_email: str = DEFAULT_SUPPORT_EMAIL,
    timezone: str = DEFAULT_TIMEZONE,
) -> Dict:
    """Return the company-info dict with tenant brand values substituted.

    `timezone` is a short human label appended after the IANA tz name in
    parens. For Oubon's America/New_York that renders as
    "America/New_York (EST/EDT)" — matching the previous hardcoded
    string. For an arbitrary tenant tz we just show the IANA name.
    """
    tz_display = timezone
    if timezone == "America/New_York":
        tz_display = "America/New_York (EST/EDT)"

    return {
        "name": brand_name,
        "website": website,
        "support_email": support_email,
        "operating_hours": {
            "weekday": "Monday-Friday, 7 AM - 9 PM",
            "weekend": "Saturday-Sunday, 10 AM - 7 PM",
            "timezone": tz_display,
        },
    }


# ============================================================================
# POLICIES
# ============================================================================

def render_refund_policy(support_email: str = DEFAULT_SUPPORT_EMAIL) -> str:
    return f"""
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
1. Email us at {support_email} with your order number
2. Describe the issue with the product
3. Confirm that you will ship the item back to us
4. We'll process eligible refunds within 24 hours
5. Refunds appear in 5-7 business days on original payment method

### Return Shipping
- Customer is responsible for return shipping costs
- We recommend using a tracked shipping method
- Keep your tracking number for reference
"""


def render_return_policy(support_email: str = DEFAULT_SUPPORT_EMAIL) -> str:
    return f"""
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
1. Email {support_email} with order number
2. We'll provide return shipping instructions
3. Ship item back with tracking
4. Refund processed within 5 business days of receiving return
"""


def render_shipping_policy(
    support_email: str = DEFAULT_SUPPORT_EMAIL,
    tracking_url: str = DEFAULT_TRACKING_URL,
) -> str:
    return f"""
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
- Track packages at: {tracking_url} or via carrier website

### Lost or Damaged Packages
- Contact us immediately at {support_email}
- Include order number and photo of damage (if applicable)
- We'll work with carrier to resolve or send replacement
"""


# These two are brand-agnostic — no substitution needed.
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

# Brand-agnostic scenario playbook.
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


# ============================================================================
# FAQ
# ============================================================================

def render_faq(tracking_url: str = DEFAULT_TRACKING_URL) -> Dict[str, str]:
    """FAQ entries with the tenant tracking URL substituted where relevant."""
    return {
        "How long does shipping take?": "Standard shipping takes 5-7 business days. Express shipping is 2-3 business days. You'll receive a tracking number within 24 hours of your order shipping.",

        "Do you ship internationally?": "Yes, we ship to select countries. International shipping takes 10-21 business days. Note that customers are responsible for any customs fees.",

        "What's your refund policy?": "We offer refunds within 15 days for quality issues (damaged, defective, wrong item). Orders $100 or less are processed automatically. Just email us with your order number and confirm you'll ship the item back.",

        "How do I track my order?": f"We'll email you a tracking number within 24 hours of shipping. You can track at {tracking_url} or directly on the carrier's website.",

        "Can I change my shipping address?": "If your order hasn't shipped yet, we can update the address. Contact us immediately with your order number and new address.",

        "Do you offer exchanges?": "We don't offer direct exchanges, but you can return the original item for a refund and place a new order for the item you'd like.",
    }


# ============================================================================
# POLICY CONTEXT — what gets fed to the AI prompt
# ============================================================================

def get_policy_context(
    brand_name: str = DEFAULT_BRAND_NAME,
    website: str = DEFAULT_WEBSITE,
    support_email: str = DEFAULT_SUPPORT_EMAIL,
    tracking_url: str = DEFAULT_TRACKING_URL,
    timezone: str = DEFAULT_TIMEZONE,
) -> str:
    """
    Get formatted policy context for AI to reference.

    Kwargs default to Oubon Shop for the single-tenant deployment.
    Multi-tenant callers (SmartReplySystem / EmailProcessor via
    AIClient) pass per-tenant values.
    """
    info = render_company_info(
        brand_name=brand_name,
        website=website,
        support_email=support_email,
        timezone=timezone,
    )

    return f"""
# {info['name']} Customer Support Policies

## Company Information
{info['name']}
Support: {info['support_email']}
Operating Hours:
- Weekdays: {info['operating_hours']['weekday']}
- Weekends: {info['operating_hours']['weekend']}

{render_refund_policy(support_email=support_email)}

{render_return_policy(support_email=support_email)}

{render_shipping_policy(support_email=support_email, tracking_url=tracking_url)}

{ORDER_STATUS_INFO}

{CUSTOMER_SERVICE_APPROACH}
"""


def get_scenario_guidance(scenario_type: str) -> dict:
    """Get specific guidance for common scenarios. Brand-agnostic."""
    return COMMON_SCENARIOS.get(scenario_type, {})


def get_faq_answer(
    question: str,
    tracking_url: str = DEFAULT_TRACKING_URL,
) -> str:
    """Get answer to common questions. Tracking URL is tenant-aware."""
    faq = render_faq(tracking_url=tracking_url)
    question_lower = question.lower()
    for faq_q, faq_a in faq.items():
        if any(word in question_lower for word in faq_q.lower().split()):
            return faq_a
    return ""


# ============================================================================
# BACKWARD-COMPAT SHIMS
# ============================================================================
# Pre-Pass-4b callers imported these as module-level constants. Rendered
# here with Oubon defaults so nothing breaks. New code should call the
# `render_*` functions directly with a tenant brand context.

COMPANY_INFO = render_company_info()
REFUND_POLICY = render_refund_policy()
RETURN_POLICY = render_return_policy()
SHIPPING_POLICY = render_shipping_policy()
FAQ = render_faq()
