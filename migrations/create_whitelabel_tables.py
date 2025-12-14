"""
White-Label SaaS Tables Migration - GROK RECOMMENDATION #19

Creates all white-label tables in the database using SQLAlchemy.

Run with:
    uv run python migrations/create_whitelabel_tables.py

Tables created:
- whitelabel_partners
- whitelabel_branding
- whitelabel_domains
- whitelabel_email_settings
- whitelabel_clients
- whitelabel_analytics

These tables enable agencies to rebrand Ospra as their own platform (B2B2C model).
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, inspect
from ospra_os.database.multi_store_models import Base
from ospra_os.database.whitelabel_models import (
    WhiteLabelPartner,
    WhiteLabelBranding,
    WhiteLabelDomain,
    WhiteLabelEmailSettings,
    WhiteLabelClient,
    WhiteLabelAnalytics
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration(database_url: str = "sqlite:///./data/ospra_os.db"):
    """
    Create white-label tables.

    Args:
        database_url: Database connection string
    """

    logger.info(f"Connecting to database: {database_url}")

    # Create engine
    engine = create_engine(database_url)

    # Check existing tables
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    logger.info(f"Existing tables: {len(existing_tables)} tables in database")

    # Tables to create
    whitelabel_tables = [
        "whitelabel_partners",
        "whitelabel_branding",
        "whitelabel_domains",
        "whitelabel_email_settings",
        "whitelabel_clients",
        "whitelabel_analytics"
    ]

    # Check which tables need to be created
    tables_to_create = [t for t in whitelabel_tables if t not in existing_tables]

    if not tables_to_create:
        logger.info("✅ All white-label tables already exist")
        logger.info("")
        logger.info("Existing white-label tables:")
        for table in whitelabel_tables:
            columns = inspector.get_columns(table)
            logger.info(f"  - {table} ({len(columns)} columns)")
        return

    logger.info(f"Creating tables: {tables_to_create}")

    # Create only white-label tables
    # (avoid triggering validation errors from other unrelated tables)
    WhiteLabelPartner.__table__.create(engine, checkfirst=True)
    WhiteLabelBranding.__table__.create(engine, checkfirst=True)
    WhiteLabelDomain.__table__.create(engine, checkfirst=True)
    WhiteLabelEmailSettings.__table__.create(engine, checkfirst=True)
    WhiteLabelClient.__table__.create(engine, checkfirst=True)
    WhiteLabelAnalytics.__table__.create(engine, checkfirst=True)

    # Verify creation
    inspector = inspect(engine)
    new_tables = inspector.get_table_names()

    created_tables = [t for t in whitelabel_tables if t in new_tables]

    logger.info("")
    logger.info(f"✅ Created {len(created_tables)} white-label tables:")
    for table in created_tables:
        # Get columns
        columns = inspector.get_columns(table)
        column_names = [col['name'] for col in columns]
        logger.info(f"   - {table} ({len(column_names)} columns)")

    # Show some sample columns for key tables
    logger.info("")
    logger.info("Key table details:")

    # Partners table
    partner_cols = inspector.get_columns("whitelabel_partners")
    logger.info(f"  whitelabel_partners: company_name, slug, api_key, plan, max_clients, status")

    # Branding table
    branding_cols = inspector.get_columns("whitelabel_branding")
    logger.info(f"  whitelabel_branding: brand_name, logos (4), colors (11), fonts (2)")

    # Domain table
    domain_cols = inspector.get_columns("whitelabel_domains")
    logger.info(f"  whitelabel_domains: domain, dns_verified, ssl_status, cname_target")

    # Clients table
    client_cols = inspector.get_columns("whitelabel_clients")
    logger.info(f"  whitelabel_clients: partner_id, user_id, plan, is_active")

    logger.info("")
    logger.info("=" * 70)
    logger.info("WHITE-LABEL SAAS MIGRATION COMPLETE - GROK RECOMMENDATION #19")
    logger.info("=" * 70)
    logger.info("")
    logger.info("Next steps:")
    logger.info("1. Register router in ospra_os/main.py")
    logger.info("2. Add middleware to main app")
    logger.info("3. Test API endpoints at /api/whitelabel/*")
    logger.info("")
    logger.info("Example API routes:")
    logger.info("  POST   /api/whitelabel/partners - Create partner (admin)")
    logger.info("  GET    /api/whitelabel/partner/branding - Get branding (partner)")
    logger.info("  PUT    /api/whitelabel/partner/branding - Update branding (partner)")
    logger.info("  POST   /api/whitelabel/partner/domain - Configure domain (partner)")
    logger.info("  GET    /api/whitelabel/branding - Get branding for request (public)")
    logger.info("")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Create white-label SaaS tables (GROK #19)"
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default="sqlite:///./data/ospra_os.db",
        help="Database URL (default: sqlite:///./data/ospra_os.db)"
    )

    args = parser.parse_args()

    try:
        run_migration(args.database_url)
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
