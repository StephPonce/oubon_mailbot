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


def _products_columns() -> set:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("products")}


def _products_indexes() -> set:
    return {i["name"] for i in sa.inspect(op.get_bind()).get_indexes("products")}


def upgrade() -> None:
    # Guarded like 013: several code paths call Base.metadata.create_all, and a
    # table built that way already carries these columns. An unguarded
    # add_column would then raise and block the deploy.
    cols = _products_columns()
    if "shopify_product_id" not in cols:
        op.add_column("products", sa.Column("shopify_product_id", sa.String(64), nullable=True))
    if "product_key" not in cols:
        op.add_column("products", sa.Column("product_key", sa.String(64), nullable=True))

    idx = _products_indexes()
    if "ix_products_shopify_product_id" not in idx:
        op.create_index("ix_products_shopify_product_id", "products", ["shopify_product_id"])
    if "ix_products_product_key" not in idx:
        op.create_index("ix_products_product_key", "products", ["product_key"])


def downgrade() -> None:
    idx = _products_indexes()
    if "ix_products_product_key" in idx:
        op.drop_index("ix_products_product_key", table_name="products")
    if "ix_products_shopify_product_id" in idx:
        op.drop_index("ix_products_shopify_product_id", table_name="products")

    cols = _products_columns()
    if "product_key" in cols:
        op.drop_column("products", "product_key")
    if "shopify_product_id" in cols:
        op.drop_column("products", "shopify_product_id")
