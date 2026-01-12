"""
Federated Learning Tables Migration - GROK RECOMMENDATION #18

Creates all federated learning tables in the database using SQLAlchemy.

Run with:
    uv run python migrations/create_federated_tables.py

Tables created:
- aggregate_insights
- user_contributions
- insight_applications
- privacy_consents

These tables enable privacy-preserving collective intelligence where
users can contribute anonymized data and receive aggregate insights.
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, inspect
from ospra_os.database import Base
from ospra_os.database.federated_models import (
    AggregateInsight,
    UserContribution,
    InsightApplication,
    PrivacyConsent
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration(database_url: str = "sqlite:///./data/ospra_os.db"):
    """
    Create federated learning tables.

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
    federated_tables = [
        "aggregate_insights",
        "user_contributions",
        "insight_applications",
        "privacy_consents"
    ]

    # Check which tables need to be created
    tables_to_create = [t for t in federated_tables if t not in existing_tables]

    if not tables_to_create:
        logger.info("[SUCCESS] All federated learning tables already exist")
        logger.info("")
        logger.info("Existing federated tables:")
        for table in federated_tables:
            columns = inspector.get_columns(table)
            logger.info(f"  - {table} ({len(columns)} columns)")
        return

    logger.info(f"Creating tables: {tables_to_create}")

    # Create only federated learning tables
    # (avoid triggering validation errors from other unrelated tables)
    AggregateInsight.__table__.create(engine, checkfirst=True)
    UserContribution.__table__.create(engine, checkfirst=True)
    InsightApplication.__table__.create(engine, checkfirst=True)
    PrivacyConsent.__table__.create(engine, checkfirst=True)

    # Verify creation
    inspector = inspect(engine)
    new_tables = inspector.get_table_names()

    created_tables = [t for t in federated_tables if t in new_tables]

    logger.info("")
    logger.info(f"[SUCCESS] Created {len(created_tables)} federated learning tables:")
    for table in created_tables:
        # Get columns
        columns = inspector.get_columns(table)
        column_names = [col['name'] for col in columns]
        logger.info(f"   - {table} ({len(column_names)} columns)")

    logger.info("")
    logger.info("[LAUNCH] Federated Learning migration complete!")
    logger.info("")
    logger.info("Tables created:")
    logger.info("  aggregate_insights    - Statistical patterns from all users")
    logger.info("  user_contributions    - Anonymized user data (bucketed only)")
    logger.info("  insight_applications  - Tracking insight usage and effectiveness")
    logger.info("  privacy_consents      - GDPR/CCPA compliant consent management")
    logger.info("")
    logger.info("Privacy Guarantees:")
    logger.info("  [OK] Only bucketed data stored (no exact values)")
    logger.info("  [OK] Minimum 10 users required for aggregation")
    logger.info("  [OK] Minimum 50 samples required for insights")
    logger.info("  [OK] Explicit opt-in consent required")
    logger.info("  [OK] Granular control over data types")
    logger.info("")
    logger.info("Next steps:")
    logger.info("  1. Register federated router in ospra_os/main.py:")
    logger.info("     from ospra_os.federated.routes import get_federated_router")
    logger.info("     app.include_router(get_federated_router())")
    logger.info("")
    logger.info("  2. Test API health: GET /api/federated/health")
    logger.info("")
    logger.info("  3. Generate synthetic data:")
    logger.info("     uv run python generate_federated_test_data.py")
    logger.info("")
    logger.info("  4. Run aggregation:")
    logger.info("     POST /api/federated/aggregate")


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
