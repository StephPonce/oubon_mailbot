"""
Fulfillment persistence (Section B band 2, T16/T18/T19).

The engine's ``_save_fulfillment_record`` has always tried to import
``ospra_os.fulfillment.models.FulfillmentRecord`` — which never existed, so
every record silently fell back to a JSON file with no uniqueness guarantees.
This model makes the record real and carries the idempotency constraint that
prevents webhook retries from double-ordering with suppliers.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, JSON, String, Text

from .base import Base


class FulfillmentRecord(Base):
    """One supplier-fulfillment attempt for one Shopify line item.

    ``idempotency_key`` = ``{shopify_order_id}:{line_item_id}`` and is UNIQUE:
    inserting the row is the atomic claim that this line item is being
    fulfilled. A webhook retry hits the constraint and is skipped instead of
    placing a second supplier order (T16).
    """

    __tablename__ = "fulfillment_records"

    id = Column(Integer, primary_key=True, index=True)

    idempotency_key = Column(String(255), nullable=False, unique=True, index=True)

    shopify_order_id = Column(String(64), nullable=False, index=True)
    shopify_order_number = Column(String(64), nullable=True)
    line_item_id = Column(String(64), nullable=True)

    product_id = Column(String(64), nullable=True)
    product_name = Column(String(512), nullable=True)
    quantity = Column(Integer, default=1)
    order_value = Column(Float, nullable=True)  # customer-facing line value (T19 ceiling)

    supplier_type = Column(String(50), nullable=True)
    supplier_order_id = Column(String(128), nullable=True)
    supplier_url = Column(Text, nullable=True)

    # pending/processing/ordered/possibly_placed/failed/manual/shipped (T18
    # adds possibly_placed: the supplier call went out but the outcome is
    # unknown — needs human review, must never be blind-retried)
    status = Column(String(50), nullable=False, default="pending", index=True)
    error_message = Column(Text, nullable=True)

    shipping_address = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return (
            f"<FulfillmentRecord(key='{self.idempotency_key}', "
            f"status='{self.status}', supplier_order_id='{self.supplier_order_id}')>"
        )
