"""
G4: Complete Feedback Loop Tables Migration

Creates all G4 feedback loop tables in the database using SQLAlchemy.

Run with:
    uv run python migrations/create_g4_feedback_tables.py

Tables created:
- product_performance (daily sales snapshots from Shopify)
- recommendation_outcomes (AI predictions vs reality tracking)
- ai_learning_events (learning signals from outcomes)
- confidence_calibration (accuracy tracking - does 80% confidence = 80% success?)
- niche_learning (per-niche performance stats)
- global_learning_weights (baseline AI weights learned from all users)
- personal_learning_weights (user-specific AI weights)

These tables enable the AI to learn from real sales performance data,
transforming Ospra from "AI that guesses" to "AI that proves it works with real data."
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, inspect
from ospra_os.database.multi_store_models import Base
from ospra_os.database.performance_models import (
    ProductPerformance,
    RecommendationOutcome,
    AILearningEvent,
    ConfidenceCalibration,
    NicheLearning,
    GlobalLearningWeights,
    PersonalLearningWeights
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration(database_url: str = "sqlite:///./data/ospra_os.db"):
    """
    Create G4 feedback loop tables.

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
    g4_tables = [
        "product_performance",
        "recommendation_outcomes",
        "ai_learning_events",
        "confidence_calibration",
        "niche_learning",
        "global_learning_weights",
        "personal_learning_weights"
    ]

    # Check which tables need to be created
    tables_to_create = [t for t in g4_tables if t not in existing_tables]

    if not tables_to_create:
        logger.info("[SUCCESS] All G4 feedback loop tables already exist")
        logger.info("")
        logger.info("Existing G4 feedback loop tables:")
        for table in g4_tables:
            columns = inspector.get_columns(table)
            logger.info(f"  - {table} ({len(columns)} columns)")
        return

    logger.info(f"Creating tables: {tables_to_create}")

    # Create only G4 feedback loop tables
    # (avoid triggering validation errors from other unrelated tables)
    ProductPerformance.__table__.create(engine, checkfirst=True)
    RecommendationOutcome.__table__.create(engine, checkfirst=True)
    AILearningEvent.__table__.create(engine, checkfirst=True)
    ConfidenceCalibration.__table__.create(engine, checkfirst=True)
    NicheLearning.__table__.create(engine, checkfirst=True)
    GlobalLearningWeights.__table__.create(engine, checkfirst=True)
    PersonalLearningWeights.__table__.create(engine, checkfirst=True)

    # Verify creation
    inspector = inspect(engine)
    new_tables = inspector.get_table_names()

    created_tables = [t for t in g4_tables if t in new_tables]

    logger.info("")
    logger.info("[SUCCESS] G4 Feedback Loop Tables Created:")
    logger.info("")

    for table in created_tables:
        columns = inspector.get_columns(table)
        logger.info(f"  [OK] {table}")
        logger.info(f"    Columns: {len(columns)}")
        for col in columns[:5]:  # Show first 5 columns
            logger.info(f"      - {col['name']}: {col['type']}")
        if len(columns) > 5:
            logger.info(f"      ... and {len(columns) - 5} more columns")
        logger.info("")

    logger.info("=" * 70)
    logger.info("[LAUNCH] G4: COMPLETE FEEDBACK LOOP - MIGRATION COMPLETE")
    logger.info("=" * 70)
    logger.info("")
    logger.info("What this enables:")
    logger.info("")
    logger.info("  1. AI learns from REAL sales data (not just guesses)")
    logger.info("  2. Shows 'AI has 78% success rate for you'")
    logger.info("  3. Personalizes to each user's success patterns")
    logger.info("  4. Tracks niche-specific performance")
    logger.info("  5. Calibrates confidence scores to actual outcomes")
    logger.info("")
    logger.info("Next steps:")
    logger.info("")
    logger.info("  1. Deploy products and wait 7 days for sales data")
    logger.info("  2. Run: POST /api/feedback/sync (fetch sales from Shopify)")
    logger.info("  3. Run: POST /api/feedback/evaluate (compare AI vs reality)")
    logger.info("  4. Run: POST /api/feedback/process-learning (update AI weights)")
    logger.info("  5. View: GET /api/feedback/learning-stats (see AI's success rate)")
    logger.info("")
    logger.info("Or let Celery Beat automate it:")
    logger.info("  - Sales sync: Every 6 hours")
    logger.info("  - Evaluation: Daily at 2 AM")
    logger.info("  - Learning: Daily at 3 AM")
    logger.info("")


if __name__ == "__main__":
    run_migration()
