"""Smart response caching to reduce AI costs.

Brand parameterization (Cleanup Pass 4 SaaS refactor):
  FAQ templates use a `{signature}` placeholder. `get_faq_response` fills
  it at render time with the caller-supplied brand signature (default
  "— Oubon Shop Support"). Oubon's deployment renders identically to
  before; multi-tenant callers pass their own `brand_name` to get
  tenant-specific signatures.
"""
from typing import Optional, Dict
from datetime import datetime, timedelta, timezone
import hashlib
import json

from ospra_os.tenancy.brand import DEFAULT_BRAND_NAME


class ResponseCache:
    """
    Cache AI responses for similar questions.
    Reduces costs and improves response time.
    """

    def __init__(self, ttl_hours: int = 24):
        self.cache: Dict[str, Dict] = {}
        self.ttl_hours = ttl_hours

    def _generate_key(self, subject: str, body: str) -> str:
        """Generate cache key from email content."""
        # Normalize text
        text = f"{subject.lower().strip()} {body.lower().strip()}"

        # Remove order numbers, emails, names (keep the question generic)
        import re
        text = re.sub(r'#?\d{4,}', '[ORDER]', text)
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
        text = re.sub(r'\b[A-Z][a-z]+\b', '[NAME]', text)  # Simple name detection

        # Generate hash
        return hashlib.md5(text.encode()).hexdigest()

    def get(self, subject: str, body: str) -> Optional[str]:
        """Get cached response if available and not expired."""
        key = self._generate_key(subject, body)

        if key in self.cache:
            cached = self.cache[key]
            expires_at = cached["expires_at"]

            if datetime.now(timezone.utc) < expires_at:
                print(f" Cache hit! Saved AI call")
                return cached["response"]
            else:
                # Expired, remove from cache
                del self.cache[key]

        return None

    def set(self, subject: str, body: str, response: str):
        """Cache a response."""
        key = self._generate_key(subject, body)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=self.ttl_hours)

        self.cache[key] = {
            "response": response,
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc),
        }

        print(f" Cached response (expires in {self.ttl_hours}h)")

    def clear_expired(self):
        """Remove expired entries from cache."""
        now = datetime.now(timezone.utc)
        expired_keys = [
            key for key, value in self.cache.items()
            if value["expires_at"] < now
        ]

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            print(f" Cleared {len(expired_keys)} expired cache entries")

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            "cached_responses": len(self.cache),
            "oldest_entry": min(
                (v["created_at"] for v in self.cache.values()),
                default=None
            ),
        }


# Default tracking hostname (Oubon's). Multi-tenant callers can override
# via `tracking_host` when calling `get_faq_response` or `get_cached_response`.
DEFAULT_TRACKING_HOST = "oubonshop.com/track"

# FAQ response templates. `{signature}` and `{tracking_host}` are filled at
# render time by `get_faq_response`. The templates are intentionally static
# at module load so they can be hashed/cached, then formatted per-request.
FAQ_CACHE = {
    "refund_policy": """We offer refunds within 15 days for quality issues (damaged, defective, wrong item, not as described). Orders $100 or less are processed automatically when you confirm you'll ship the item back. For orders over $100 or older than 15 days, our team will review within 24-48 hours.

Refunds typically appear in 5-7 business days on your original payment method.

{signature}""",

    "shipping_time": """Our standard shipping takes 5-7 business days within the United States. Express shipping is available for 2-3 business day delivery.

You'll receive a tracking number within 24 hours of your order shipping, and you can track your package at {tracking_host} or directly on the carrier's website.

{signature}""",

    "return_process": """Returns are accepted within 30 days of delivery. To start a return:

1. Email us with your order number
2. We'll provide return shipping instructions
3. Ship the item back with tracking
4. Refund processed within 5 business days of receiving the return

Items must be in original condition with tags attached.

{signature}""",

    "international_shipping": """Yes, we ship to select countries internationally! International shipping typically takes 10-21 business days depending on the destination.

Please note that customers are responsible for any customs fees or duties that may apply.

{signature}""",

    "order_tracking": """You can track your order in two ways:

1. Visit {tracking_host} and enter your order number
2. Use the tracking number from your shipping confirmation email on the carrier's website

If you need help finding your order number, please reply with the email address you used at checkout.

{signature}""",
}


def _render_faq(
    template_key: str,
    brand_name: str,
    tracking_host: str,
) -> str:
    """Fill a FAQ template with the given brand signature + tracking host."""
    template = FAQ_CACHE[template_key]
    return template.format(
        signature=f"— {brand_name} Support",
        tracking_host=tracking_host,
    )


def get_faq_response(
    subject: str,
    body: str,
    brand_name: str = DEFAULT_BRAND_NAME,
    tracking_host: str = DEFAULT_TRACKING_HOST,
) -> Optional[str]:
    """Check if this matches a common FAQ; render with the caller's brand."""
    text = f"{subject} {body}".lower()

    def _render(key: str) -> str:
        return _render_faq(key, brand_name=brand_name, tracking_host=tracking_host)

    # Check for FAQ patterns
    if any(word in text for word in ["refund policy", "refund process", "how to refund", "can i get refund"]):
        return _render("refund_policy")

    if any(word in text for word in ["how long shipping", "shipping time", "when will arrive", "delivery time"]):
        return _render("shipping_time")

    if any(word in text for word in ["how to return", "return process", "send back"]):
        return _render("return_process")

    if any(word in text for word in ["international shipping", "ship internationally", "ship to"]):
        return _render("international_shipping")

    if any(word in text for word in ["track order", "track my order", "tracking", "where is"]):
        return _render("order_tracking")

    return None


# Global cache instance
_cache = ResponseCache(ttl_hours=24)


def get_cached_response(
    subject: str,
    body: str,
    brand_name: str = DEFAULT_BRAND_NAME,
    tracking_host: str = DEFAULT_TRACKING_HOST,
) -> Optional[str]:
    """Try to get a cached or FAQ response.

    `brand_name` / `tracking_host` are used only for FAQ template rendering
    — the AI response cache is keyed on the email content, not the brand.
    """
    # Check FAQ first (instant)
    faq = get_faq_response(subject, body, brand_name=brand_name, tracking_host=tracking_host)
    if faq:
        print(" FAQ response used (instant, no AI cost)")
        return faq

    # Check cache
    return _cache.get(subject, body)


def cache_response(subject: str, body: str, response: str):
    """Cache an AI response for future use."""
    _cache.set(subject, body, response)


def clear_expired_cache():
    """Clear expired cache entries."""
    _cache.clear_expired()


def get_cache_stats() -> Dict:
    """Get cache statistics."""
    return _cache.get_stats()
