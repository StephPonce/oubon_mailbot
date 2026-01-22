"""
Create Learning Performance Tables
===================================

Creates the complete G4 feedback loop tables for AI self-learning:
- Product performance tracking
- Recommendation outcomes
- AI learning events
- Confidence calibration
- Niche learning
- Global and personal learning weights

Run with: uv run python migrations/create_learning_tables.py
"""

from ospra_os.database.connection import get_engine
from ospra_os.database.performance_models import (
    ProductPerformance,
    RecommendationOutcome,
    AILearningEvent,
    ConfidenceCalibration,
    NicheLearning,
    GlobalLearningWeights,
    PersonalLearningWeights,
)
from ospra_os.database.base import Base

def create_tables():
    """Create all learning/performance tracking tables."""
    print("🔧 Creating learning performance tables...")

    # Get engine (handles database URL internally)
    engine = get_engine()
    print(f"📊 Database: {str(engine.url).split('@')[-1] if '@' in str(engine.url) else 'SQLite'}")

    # Create all tables defined in performance_models
    print("\n📋 Creating tables:")
    print("  - product_performance")
    print("  - recommendation_outcomes")
    print("  - ai_learning_events")
    print("  - confidence_calibration")
    print("  - niche_learning")
    print("  - global_learning_weights")
    print("  - personal_learning_weights")

    Base.metadata.create_all(
        bind=engine,
        tables=[
            ProductPerformance.__table__,
            RecommendationOutcome.__table__,
            AILearningEvent.__table__,
            ConfidenceCalibration.__table__,
            NicheLearning.__table__,
            GlobalLearningWeights.__table__,
            PersonalLearningWeights.__table__,
        ],
        checkfirst=True
    )

    print("\n✅ Learning tables created successfully!")
    print("\nThese tables enable:")
    print("  • Real-world performance tracking")
    print("  • AI recommendation outcome analysis")
    print("  • Automated learning from successes/failures")
    print("  • Confidence score calibration")
    print("  • Niche-specific learning")
    print("  • Personalized AI weights per user")
    print("\n🎯 Your AI can now learn from real sales data!")

if __name__ == "__main__":
    create_tables()
