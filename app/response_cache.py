"""Smart response caching to reduce AI costs."""
from typing import Optional, Dict
from datetime import datetime, timedelta
import hashlib
import json


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

            if datetime.utcnow() < expires_at:
                print(f"💾 Cache hit! Saved AI call")
                return cached["response"]
            else:
                # Expired, remove from cache
                del self.cache[key]

        return None

    def set(self, subject: str, body: str, response: str):
        """Cache a response."""
        key = self._generate_key(subject, body)
        expires_at = datetime.utcnow() + timedelta(hours=self.ttl_hours)

        self.cache[key] = {
            "response": response,
            "expires_at": expires_at,
            "created_at": datetime.utcnow(),
        }

        print(f"💾 Cached response (expires in {self.ttl_hours}h)")

    def clear_expired(self):
        """Remove expired entries from cache."""
        now = datetime.utcnow()
        expired_keys = [
            key for key, value in self.cache.items()
            if value["expires_at"] < now
        ]

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            print(f"🧹 Cleared {len(expired_keys)} expired cache entries")

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            "cached_responses": len(self.cache),
            "oldest_entry": min(
                (v["created_at"] for v in self.cache.values()),
                default=None
            ),
        }


# FAQ responses that should always be cached
FAQ_CACHE = {
    "refund_policy": """We offer refunds within 15 days for quality issues (damaged, defective, wrong item, not as described). Orders $100 or less are processed automatically when you confirm you'll ship the item back. For orders over $100 or older than 15 days, our team will review within 24-48 hours.

Refunds typically appear in 5-7 business days on your original payment method.

— Oubon Shop Support""",

    "shipping_time": """Our standard shipping takes 5-7 business days within the United States. Express shipping is available for 2-3 business day delivery.

You'll receive a tracking number within 24 hours of your order shipping, and you can track your package at oubonshop.com/track or directly on the carrier's website.

— Oubon Shop Support""",

    "return_process": """Returns are accepted within 30 days of delivery. To start a return:

1. Email us with your order number
2. We'll provide return shipping instructions
3. Ship the item back with tracking
4. Refund processed within 5 business days of receiving the return

Items must be in original condition with tags attached.

— Oubon Shop Support""",

    "international_shipping": """Yes, we ship to select countries internationally! International shipping typically takes 10-21 business days depending on the destination.

Please note that customers are responsible for any customs fees or duties that may apply.

— Oubon Shop Support""",

    "order_tracking": """You can track your order in two ways:

1. Visit oubonshop.com/track and enter your order number
2. Use the tracking number from your shipping confirmation email on the carrier's website

If you need help finding your order number, please reply with the email address you used at checkout.

— Oubon Shop Support""",
}


def get_faq_response(subject: str, body: str) -> Optional[str]:
    """Check if this matches a common FAQ."""
    text = f"{subject} {body}".lower()

    # Check for FAQ patterns
    if any(word in text for word in ["refund policy", "refund process", "how to refund", "can i get refund"]):
        return FAQ_CACHE["refund_policy"]

    if any(word in text for word in ["how long shipping", "shipping time", "when will arrive", "delivery time"]):
        return FAQ_CACHE["shipping_time"]

    if any(word in text for word in ["how to return", "return process", "send back"]):
        return FAQ_CACHE["return_process"]

    if any(word in text for word in ["international shipping", "ship internationally", "ship to"]):
        return FAQ_CACHE["international_shipping"]

    if any(word in text for word in ["track order", "track my order", "tracking", "where is"]):
        return FAQ_CACHE["order_tracking"]

    return None


# Global cache instance
_cache = ResponseCache(ttl_hours=24)


def get_cached_response(subject: str, body: str) -> Optional[str]:
    """Try to get a cached or FAQ response."""
    # Check FAQ first (instant)
    faq = get_faq_response(subject, body)
    if faq:
        print("📚 FAQ response used (instant, no AI cost)")
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
