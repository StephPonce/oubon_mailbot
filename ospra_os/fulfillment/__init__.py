"""
Ospra OS Auto-Fulfillment System
================================

Automatically fulfills Shopify orders by placing orders with suppliers:
- CJ Dropshipping (API integration)
- AliExpress (API or manual queue)

Exports:
- AutoFulfillmentEngine: Main fulfillment engine
- get_fulfillment_engine: Singleton accessor
- FulfillmentStatus: Order status enum
- SupplierType: Supplier type enum
"""

from ospra_os.fulfillment.auto_fulfillment import (
    AutoFulfillmentEngine,
    get_fulfillment_engine,
    FulfillmentStatus,
    SupplierType,
    FulfillmentOrder
)

__all__ = [
    "AutoFulfillmentEngine",
    "get_fulfillment_engine",
    "FulfillmentStatus",
    "SupplierType",
    "FulfillmentOrder"
]
