"""Close the prediction→outcome join: products.shopify_product_id + product_key.

Revision ID: 014
Revises: 013
Create Date: 2026-08-26 14:00:00.000000

F1 needs to attribute a Shopify order back to the product Ospra graded. That
join did not exist:

  * `products.source_product_id` holds the SUPPLIER id (AliExpress/CJ), but
    `webhooks/webhook_utils.py` filtered it with the SHOPIFY id — different id
    spaces, so the lookup never matched and every line item hit a `continue`
    labelled "wasn't from an Ospra-discovered product". Silent and total.
  * `services/sales_sync_service.py` read `Product.platform_product_id`, a
    column that exists on ProductDeployment, not Product.
  * The Shopify id was persisted only inside a JSON blob on
    `recommendation_outcomes.confidence_breakdown`, and the discovery
    `product_key` was never carried past discovery at all.

Two nullable indexed columns on the row the deploy path already writes. Both
backfill as NULL: existing rows genuinely have no recoverable key, and
inventing one would fabricate provenance the ledger is meant to prove.
"""

import sqlalchemy as sa
from alembic import op

revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("shopify_product_id", sa.String(64), nullable=True))
    op.add_column("products", sa.Column("product_key", sa.String(64), nullable=True))
    op.create_index("ix_products_shopify_product_id", "products", ["shopify_product_id"])
    op.create_index("ix_products_product_key", "products", ["product_key"])


def downgrade() -> None:
    op.drop_index("ix_products_product_key", table_name="products")
    op.drop_index("ix_products_shopify_product_id", table_name="products")
    op.drop_column("products", "product_key")
    op.drop_column("products", "shopify_product_id")
