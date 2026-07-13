"""
Webhook event idempotency (Section B band 3, T27).

Payment webhooks had no replay protection: LemonSqueezy retries (or an
attacker replaying a captured request past signature verification) applied
tier changes twice, and a processing failure still returned HTTP 200 so the
provider never retried — customer paid, never upgraded.

Inserting a row here (UNIQUE event_key) is the atomic claim on an event.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from .base import Base


class ProcessedWebhookEvent(Base):
    """One received payment-webhook delivery.

    ``event_key`` is a stable digest of provider + event body; a replayed
    delivery computes the same key, hits the UNIQUE constraint, and is
    acknowledged without being re-applied.
    """

    __tablename__ = "processed_webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), nullable=False, index=True)  # lemonsqueezy, ...
    event_key = Column(String(128), nullable=False, unique=True, index=True)
    event_name = Column(String(100), nullable=True)

    # processing → processed | failed. Failed events release the claim so the
    # provider's retry can re-attempt (we return 5xx to trigger that retry).
    status = Column(String(20), nullable=False, default="processing", index=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<ProcessedWebhookEvent({self.provider}, '{self.event_name}', {self.status})>"
