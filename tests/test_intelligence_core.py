"""
Unit Tests for Intelligence Core

Tests all 6 core modules:
- unified_context
- briefing_engine
- grade_reasoning
- progress_flow
- tier_system
- action_executor
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ospra_os.database import Base, Product, ProductStatus
from ospra_os.intelligence.unified_context import UnifiedContextBuilder
from ospra_os.intelligence.briefing_engine import BriefingEngine
from ospra_os.intelligence.grade_reasoning import GradeReasoningEngine
from ospra_os.intelligence.progress_flow import ProgressFlowTracker, LifecycleStage
from ospra_os.intelligence.tier_system import TierSystem, Tier
from ospra_os.intelligence.action_executor import ActionExecutor, ActionType


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def test_db():
    """Create in-memory test database"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Add test product
    test_product = Product(
        id=1,
        store_id=1,  # Required field
        product_name="Test Smart Watch",
        title="Test Smart Watch",
        price=49.99,
        status=ProductStatus.ACTIVE,
        velocity_score=7.5,
        social_score=85.0,
        saturation_level=35.0,
        rating=4.5,
        review_count=250
    )
    session.add(test_product)
    session.commit()

    yield session

    session.close()


# ============================================================================
# UNIFIED CONTEXT TESTS
# ============================================================================

class TestUnifiedContext:
    """Tests for UnifiedContextBuilder"""

    @pytest.mark.asyncio
    async def test_build_full_context(self, test_db):
        """Test building complete unified context"""
        builder = UnifiedContextBuilder(test_db)

        context = await builder.build_full_context(user_id=1, store_id=1)

        assert context is not None
        assert "products" in context
        assert "ads" in context
        assert "summary" in context

    @pytest.mark.asyncio
    async def test_context_caching(self, test_db):
        """Test context caching mechanism"""
        builder = UnifiedContextBuilder(test_db)

        # First call - should fetch data
        context1 = await builder.build_full_context(user_id=1)

        # Second call - should use cache
        context2 = await builder.build_full_context(user_id=1)

        assert context1 == context2

    def test_cache_invalidation(self, test_db):
        """Test cache invalidation"""
        builder = UnifiedContextBuilder(test_db)

        # Should not raise an error
        builder.invalidate_cache(user_id=1)


# ============================================================================
# BRIEFING ENGINE TESTS
# ============================================================================

class TestBriefingEngine:
    """Tests for BriefingEngine"""

    def test_briefing_engine_initialization(self, test_db):
        """Test that BriefingEngine can be initialized"""
        engine = BriefingEngine(test_db)
        assert engine is not None
        assert engine.db is not None


# ============================================================================
# GRADE REASONING TESTS
# ============================================================================

class TestGradeReasoning:
    """Tests for GradeReasoningEngine"""

    @pytest.mark.asyncio
    async def test_product_grading(self, test_db):
        """Test product grade calculation"""
        engine = GradeReasoningEngine(test_db)

        grade_data = await engine.calculate_product_grade(product_id=1)

        assert grade_data is not None
        assert "grade" in grade_data
        assert "score" in grade_data
        assert "breakdown" in grade_data
        assert grade_data["score"] >= 0
        assert grade_data["score"] <= 100

    def test_score_to_letter_conversion(self, test_db):
        """Test score to letter grade conversion"""
        engine = GradeReasoningEngine(test_db)

        # Test exact threshold matches
        assert engine._score_to_letter(95) == "A+"
        assert engine._score_to_letter(90) == "A"
        assert engine._score_to_letter(85) == "A-"
        assert engine._score_to_letter(80) == "B+"
        assert engine._score_to_letter(75) == "B"
        assert engine._score_to_letter(70) == "B-"
        assert engine._score_to_letter(65) == "C+"
        assert engine._score_to_letter(60) == "C"
        assert engine._score_to_letter(55) == "C-"
        assert engine._score_to_letter(50) == "D"
        assert engine._score_to_letter(45) == "F"
        assert engine._score_to_letter(0) == "F"

    def test_profit_potential_calculation(self, test_db):
        """Test profit potential scoring"""
        engine = GradeReasoningEngine(test_db)

        product_data = {
            "margin": 0.4,  # 40% margin
            "expected_monthly_sales": 100
        }

        profit_score = engine._calculate_profit_potential(product_data)

        assert profit_score["score"] > 0
        assert profit_score["score"] <= 30  # Max points for profit
        assert "percentage" in profit_score


# ============================================================================
# PROGRESS FLOW TESTS
# ============================================================================

class TestProgressFlow:
    """Tests for ProgressFlowTracker"""

    @pytest.mark.asyncio
    async def test_product_progress_tracking(self, test_db):
        """Test getting product progress"""
        tracker = ProgressFlowTracker(test_db)

        progress = await tracker.get_product_progress(product_id=1)

        assert progress is not None
        assert "current_stage" in progress
        assert "progress_percentage" in progress
        assert "milestones" in progress

    def test_stage_determination(self, test_db):
        """Test lifecycle stage determination"""
        tracker = ProgressFlowTracker(test_db)

        product = test_db.query(Product).first()
        stage = tracker._determine_stage(product)

        assert stage in [s.value for s in LifecycleStage]


# ============================================================================
# TIER SYSTEM TESTS
# ============================================================================

class TestTierSystem:
    """Tests for TierSystem"""

    def test_tier_system_initialization(self, test_db):
        """Test that TierSystem can be initialized"""
        tier_system = TierSystem(test_db)
        assert tier_system is not None
        assert tier_system.db is not None


# ============================================================================
# ACTION EXECUTOR TESTS
# ============================================================================

class TestActionExecutor:
    """Tests for ActionExecutor"""

    @pytest.mark.asyncio
    async def test_action_preview(self, test_db):
        """Test action preview"""
        executor = ActionExecutor(test_db)

        preview = await executor.preview_action(
            action_type=ActionType.DEPLOY_PRODUCT,
            params={"product_id": 1}
        )

        assert preview is not None
        assert "action_type" in preview
        assert "description" in preview
        assert "reversible" in preview

    @pytest.mark.asyncio
    async def test_action_execution(self, test_db):
        """Test action execution"""
        executor = ActionExecutor(test_db)

        result = await executor.execute_action(
            action_type=ActionType.DEPLOY_PRODUCT,
            params={"product_id": 1},
            user_id=1
        )

        assert result is not None
        assert result["status"] == "completed"
        assert "action_id" in result

    @pytest.mark.asyncio
    async def test_action_undo(self, test_db):
        """Test action undo"""
        executor = ActionExecutor(test_db)

        # Execute action
        execute_result = await executor.execute_action(
            action_type=ActionType.ADJUST_PRICE,
            params={"product_id": 1, "new_price": 59.99},
            user_id=1
        )

        action_id = execute_result["action_id"]

        # Undo action
        undo_result = await executor.undo_action(action_id)

        assert undo_result["success"] is True

        # Verify price was restored
        product = test_db.query(Product).first()
        assert product.price == 49.99  # Original price


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntelligenceCoreIntegration:
    """Integration tests for entire Intelligence Core"""

    @pytest.mark.asyncio
    async def test_all_engines_initialize(self, test_db):
        """Test that all Intelligence Core engines can be initialized"""
        # 1. Build unified context
        context_builder = UnifiedContextBuilder(test_db)
        assert context_builder is not None

        # 2. Briefing engine
        briefing_engine = BriefingEngine(test_db)
        assert briefing_engine is not None

        # 3. Grade engine
        grade_engine = GradeReasoningEngine(test_db)
        assert grade_engine is not None

        # 4. Progress tracker
        progress_tracker = ProgressFlowTracker(test_db)
        assert progress_tracker is not None

        # 5. Tier system
        tier_system = TierSystem(test_db)
        assert tier_system is not None

        # 6. Action executor
        executor = ActionExecutor(test_db)
        assert executor is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
