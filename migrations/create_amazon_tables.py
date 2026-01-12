"""
Amazon FBA Tables Migration - GROK RECOMMENDATION #16

Creates all Amazon FBA tables in the database using SQLAlchemy.

Run with:
    uv run python migrations/create_amazon_tables.py

Tables created:
- amazon_accounts
- amazon_listings
- amazon_orders
- amazon_order_items
- fba_shipments
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, inspect
from ospra_os.database import Base
from ospra_os.database.amazon_models import (
    AmazonAccount,
    AmazonListing,
    AmazonOrder,
    AmazonOrderItem,
    FBAShipment
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration(database_url: str = "sqlite:///./data/ospra_os.db"):
    """
    Create Amazon FBA tables.

    Args:
        database_url: Database connection string
    """

    logger.info(f"Connecting to database: {database_url}")

    # Create engine
    engine = create_engine(database_url)

    # Check existing tables
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    logger.info(f"Existing tables: {existing_tables}")

    # Tables to create
    amazon_tables = [
        "amazon_accounts",
        "amazon_listings",
        "amazon_orders",
        "amazon_order_items",
        "fba_shipments"
    ]

    # Check which tables need to be created
    tables_to_create = [t for t in amazon_tables if t not in existing_tables]

    if not tables_to_create:
        logger.info("[SUCCESS] All Amazon tables already exist")
        return

    logger.info(f"Creating tables: {tables_to_create}")

    # Create all tables defined in Base
    Base.metadata.create_all(engine)

    # Verify creation
    inspector = inspect(engine)
    new_tables = inspector.get_table_names()

    created_tables = [t for t in amazon_tables if t in new_tables]

    logger.info(f"[SUCCESS] Created {len(created_tables)} tables:")
    for table in created_tables:
        # Get columns
        columns = inspector.get_columns(table)
        column_names = [col['name'] for col in columns]
        logger.info(f"   - {table} ({len(column_names)} columns)")

    logger.info("")
    logger.info("[LAUNCH] Amazon FBA migration complete!")
    logger.info("")
    logger.info("Tables created:")
    logger.info("  amazon_accounts     - Amazon Seller Central connections")
    logger.info("  amazon_listings     - Product listings with FBA inventory")
    logger.info("  amazon_orders       - Customer orders")
    logger.info("  amazon_order_items  - Order line items")
    logger.info("  fba_shipments       - Inbound FBA shipments")
    logger.info("")
    logger.info("Next steps:")
    logger.info("  1. Register Amazon router in ospra_os/main.py")
    logger.info("  2. Test API: GET /api/amazon/health")
    logger.info("  3. Connect account: POST /api/amazon/accounts")


if __name__ == "__main__":
    import os

    # Get database URL from environment or use default
    database_url = os.getenv("DATABASE_URL", "sqlite:///./data/ospra_os.db")

    # Ensure data directory exists for SQLite
    if database_url.startswith("sqlite"):
        Path("./data").mkdir(exist_ok=True)

    try:
        run_migration(database_url)
    except Exception as e:
        logger.error(f"[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
