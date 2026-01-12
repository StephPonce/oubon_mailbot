"""
Niche Analysis Engine - Market Health, Lifecycle Tracking, Entry Timing

Analyzes product niches to determine:
- Health scores (0-100) based on multiple weighted factors
- Lifecycle stage (EMERGING, GROWTH, PEAK, DECLINE, DEAD)
- Saturation levels and competition metrics
- Entry timing recommendations (EXCELLENT, GOOD, FAIR, POOR, AVOID)
- Profitability and longevity predictions

Author: OspraOS
Date: November 2025
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy import select, func, and_, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import statistics

from ospra_os.database import (
    Niche,
    NicheSnapshot,
    Product,
    ProductIntelligence,
    ProductSaturation,
    RankingHistory,
    LifecycleStage,
    EntryTiming,
    RiskLevel,
    get_multi_store_session
)

logger = logging.getLogger(__name__)


class NicheAnalyzer:
    """
    Comprehensive niche analysis engine.

    Health Score Formula:
    - Trend Momentum (30%): Is demand growing?
    - Inverse Saturation (25%): How crowded is it?
    - Profit Potential (25%): Can you make money?
    - Longevity Score (20%): Will it last?

    Lifecycle Stages:
    - EMERGING: Low competition, growing interest, entry timing EXCELLENT
    - GROWTH: Accelerating demand, moderate competition, entry timing GOOD
    - PEAK: Maximum demand, high competition, entry timing FAIR
    - DECLINE: Decreasing demand, oversaturated, entry timing POOR
    - DEAD: Minimal demand, avoid completely, entry timing AVOID
    """

    # Scoring weights (must sum to 1.0)
    WEIGHTS = {
        "trend_momentum": 0.30,
        "inverse_saturation": 0.25,
        "profit_potential": 0.25,
        "longevity_score": 0.20
    }

    # Lifecycle stage thresholds based on health score
    LIFECYCLE_THRESHOLDS = {
        "EMERGING": (70, 100),    # High health, low competition
        "GROWTH": (50, 69),        # Good health, moderate competition
        "PEAK": (30, 49),          # Fair health, high competition
        "DECLINE": (10, 29),       # Poor health, oversaturated
        "DEAD": (0, 9)             # Minimal viability
    }

    # Entry timing score ranges
    ENTRY_TIMING_RANGES = {
        EntryTiming.EXCELLENT: (80, 100),
        EntryTiming.GOOD: (60, 79),
        EntryTiming.FAIR: (40, 59),
        EntryTiming.POOR: (20, 39),
        EntryTiming.AVOID: (0, 19)
    }

    # Saturation level thresholds
    SATURATION_LEVELS = {
        "LOW": (0, 25),
        "MODERATE": (26, 50),
        "HIGH": (51, 75),
        "CRITICAL": (76, 100)
    }

    def __init__(self, database_url: str):
        """
        Initialize the NicheAnalyzer.

        Args:
            database_url: Database connection string (SQLite or PostgreSQL)
        """
        self.database_url = database_url

        # Convert to async URL
        if database_url.startswith("sqlite://"):
            async_url = database_url.replace("sqlite://", "sqlite+aiosqlite://")
        elif database_url.startswith("postgresql://"):
            async_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
        else:
            async_url = database_url

        self.engine = create_async_engine(async_url, echo=False)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

        logger.info("NicheAnalyzer initialized")

    async def analyze_niche(self, niche_id: str, store_snapshot: bool = True) -> Dict:
        """
        Perform comprehensive niche analysis with all metrics.

        Args:
            niche_id: Niche identifier (e.g., "smart_home", "fitness")
            store_snapshot: Whether to store results in NicheSnapshot table

        Returns:
            Complete analysis dict with health score, lifecycle stage, recommendations
        """
        logger.info(f"[SEARCH] Analyzing niche: {niche_id}")

        async with self.async_session() as session:
            # Get or create niche record
            niche = await self._get_or_create_niche(session, niche_id)

            # Calculate all metrics
            trend_momentum = await self._calculate_trend_momentum(session, niche_id)
            saturation_data = await self._calculate_saturation(session, niche_id)
            profit_data = await self._calculate_profit_potential(session, niche_id)
            longevity_data = await self._calculate_longevity(session, niche_id)

            # Calculate composite health score
            health_score = (
                (trend_momentum["score"] * self.WEIGHTS["trend_momentum"]) +
                (saturation_data["inverse_score"] * self.WEIGHTS["inverse_saturation"]) +
                (profit_data["score"] * self.WEIGHTS["profit_potential"]) +
                (longevity_data["score"] * self.WEIGHTS["longevity_score"])
            )

            # Determine lifecycle stage
            lifecycle_stage = self._determine_lifecycle_stage(
                health_score,
                trend_momentum["score"],
                saturation_data["saturation_score"]
            )

            # Evaluate entry timing
            entry_data = self._evaluate_entry_timing(
                health_score,
                lifecycle_stage,
                saturation_data["saturation_score"],
                profit_data["avg_margin"]
            )

            # Get competitor analysis
            competitor_data = await self._analyze_competitors(session, niche_id)

            # Get top products in niche
            top_products = await self._get_top_products(session, niche_id, limit=5)

            # Generate recommendations
            recommendations = self._generate_recommendations(
                niche_id,
                health_score,
                lifecycle_stage,
                saturation_data,
                profit_data,
                trend_momentum
            )

            # Get previous snapshot for comparison
            previous_snapshot = await self._get_previous_snapshot(session, niche_id)
            health_score_change = 0.0
            stage_changed = False

            if previous_snapshot:
                health_score_change = health_score - previous_snapshot.health_score
                stage_changed = (previous_snapshot.lifecycle_stage.value != lifecycle_stage.value)

            # Build complete analysis
            analysis = {
                "niche_id": niche_id,
                "niche_name": niche.name,
                "analyzed_at": datetime.utcnow().isoformat(),

                # Core scores
                "health_score": round(health_score, 2),
                "lifecycle_stage": lifecycle_stage.value,

                # Component scores
                "trend_momentum": {
                    "score": round(trend_momentum["score"], 2),
                    "search_volume": trend_momentum.get("search_volume", 0),
                    "change_30d": round(trend_momentum.get("change_30d", 0), 2),
                    "change_90d": round(trend_momentum.get("change_90d", 0), 2),
                    "direction": trend_momentum.get("direction", "stable")
                },

                "saturation": {
                    "score": round(saturation_data["saturation_score"], 2),
                    "level": saturation_data["saturation_level"],
                    "seller_count": saturation_data["seller_count"],
                    "new_sellers_30d": saturation_data.get("new_sellers_30d", 0),
                    "inverse_score": round(saturation_data["inverse_score"], 2)
                },

                "profitability": {
                    "score": round(profit_data["score"], 2),
                    "avg_margin": round(profit_data["avg_margin"], 2),
                    "margin_trend": profit_data["margin_trend"],
                    "price_pressure": profit_data["price_pressure"]
                },

                "longevity": {
                    "score": round(longevity_data["score"], 2),
                    "is_seasonal": longevity_data["is_seasonal"],
                    "stability": round(longevity_data["stability"], 2),
                    "predicted_lifespan": longevity_data["predicted_lifespan"]
                },

                # Entry recommendation
                "entry_timing": {
                    "score": round(entry_data["score"], 2),
                    "timing": entry_data["timing"].value,
                    "should_enter": entry_data["should_enter"],
                    "risk_level": entry_data["risk_level"].value,
                    "roi_estimate": entry_data["roi_estimate"],
                    "reasoning": entry_data["reasoning"]
                },

                # Competitor analysis
                "competitors": {
                    "top_competitors": competitor_data["top_competitors"],
                    "barrier_to_entry": competitor_data["barrier_to_entry"],
                    "avg_reviews": competitor_data["avg_reviews"]
                },

                # Top products
                "top_products": top_products,

                # Historical comparison
                "changes": {
                    "health_score_change": round(health_score_change, 2),
                    "stage_changed": stage_changed,
                    "previous_stage": previous_snapshot.lifecycle_stage.value if previous_snapshot else None
                },

                # Strategic recommendations
                "recommendations": recommendations
            }

            # Store snapshot if requested
            if store_snapshot:
                await self._store_snapshot(session, niche, analysis)

            # Update niche cached metrics
            niche.current_health_score = health_score
            niche.current_lifecycle_stage = lifecycle_stage
            niche.current_entry_timing = entry_data["timing"]
            niche.updated_at = datetime.utcnow()
            await session.commit()

            logger.info(f"Niche analysis complete: {niche_id} - Health: {health_score:.1f}, Stage: {lifecycle_stage.value}")

            return analysis

    async def calculate_health_score(self, niche_id: str) -> float:
        """
        Calculate composite health score for a niche.

        Args:
            niche_id: Niche identifier

        Returns:
            Health score (0-100)
        """
        async with self.async_session() as session:
            trend_momentum = await self._calculate_trend_momentum(session, niche_id)
            saturation_data = await self._calculate_saturation(session, niche_id)
            profit_data = await self._calculate_profit_potential(session, niche_id)
            longevity_data = await self._calculate_longevity(session, niche_id)

            health_score = (
                (trend_momentum["score"] * self.WEIGHTS["trend_momentum"]) +
                (saturation_data["inverse_score"] * self.WEIGHTS["inverse_saturation"]) +
                (profit_data["score"] * self.WEIGHTS["profit_potential"]) +
                (longevity_data["score"] * self.WEIGHTS["longevity_score"])
            )

            return round(health_score, 2)

    async def determine_lifecycle_stage(self, niche_id: str) -> str:
        """
        Identify current lifecycle stage for a niche.

        Args:
            niche_id: Niche identifier

        Returns:
            Lifecycle stage string (emerging/growth/peak/decline/dead)
        """
        health_score = await self.calculate_health_score(niche_id)

        async with self.async_session() as session:
            trend_momentum = await self._calculate_trend_momentum(session, niche_id)
            saturation_data = await self._calculate_saturation(session, niche_id)

            stage = self._determine_lifecycle_stage(
                health_score,
                trend_momentum["score"],
                saturation_data["saturation_score"]
            )

            return stage.value

    async def evaluate_entry_timing(self, niche_id: str) -> Dict:
        """
        Evaluate whether user should enter this niche now.

        Args:
            niche_id: Niche identifier

        Returns:
            Entry timing analysis with recommendation
        """
        health_score = await self.calculate_health_score(niche_id)

        async with self.async_session() as session:
            saturation_data = await self._calculate_saturation(session, niche_id)
            profit_data = await self._calculate_profit_potential(session, niche_id)

            # Determine lifecycle stage
            trend_momentum = await self._calculate_trend_momentum(session, niche_id)
            lifecycle_stage = self._determine_lifecycle_stage(
                health_score,
                trend_momentum["score"],
                saturation_data["saturation_score"]
            )

            entry_data = self._evaluate_entry_timing(
                health_score,
                lifecycle_stage,
                saturation_data["saturation_score"],
                profit_data["avg_margin"]
            )

            return {
                "niche_id": niche_id,
                "entry_timing_score": round(entry_data["score"], 2),
                "entry_timing": entry_data["timing"].value,
                "should_enter": entry_data["should_enter"],
                "risk_level": entry_data["risk_level"].value,
                "roi_estimate": entry_data["roi_estimate"],
                "reasoning": entry_data["reasoning"],
                "health_score": round(health_score, 2),
                "saturation_level": saturation_data["saturation_level"]
            }

    async def get_all_niches(self, sort_by: str = "health_score") -> List[Dict]:
        """
        Get all tracked niches with current scores.

        Args:
            sort_by: Sort field (health_score, name, lifecycle_stage)

        Returns:
            List of niches with key metrics
        """
        async with self.async_session() as session:
            stmt = select(Niche).where(Niche.is_active == True)

            # Apply sorting
            if sort_by == "health_score":
                stmt = stmt.order_by(desc(Niche.current_health_score))
            elif sort_by == "name":
                stmt = stmt.order_by(Niche.name)
            elif sort_by == "lifecycle_stage":
                stmt = stmt.order_by(Niche.current_lifecycle_stage)

            result = await session.execute(stmt)
            niches = result.scalars().all()

            return [
                {
                    "niche_id": n.niche_id,
                    "name": n.name,
                    "description": n.description,
                    "health_score": n.current_health_score,
                    "lifecycle_stage": n.current_lifecycle_stage.value if n.current_lifecycle_stage else None,
                    "entry_timing": n.current_entry_timing.value if n.current_entry_timing else None,
                    "tracked_since": n.tracked_since.isoformat() if n.tracked_since else None,
                    "last_updated": n.updated_at.isoformat() if n.updated_at else None
                }
                for n in niches
            ]

    async def get_trending_niches(self, limit: int = 10) -> List[Dict]:
        """
        Get niches with improving health scores.

        Args:
            limit: Number of niches to return

        Returns:
            List of trending niches with growth metrics
        """
        async with self.async_session() as session:
            # Get niches with recent snapshots showing positive change
            seven_days_ago = datetime.utcnow() - timedelta(days=7)

            stmt = select(NicheSnapshot).where(
                NicheSnapshot.snapshot_date >= seven_days_ago
            ).order_by(
                desc(NicheSnapshot.health_score_change)
            ).limit(limit)

            result = await session.execute(stmt)
            snapshots = result.scalars().all()

            trending = []
            for snapshot in snapshots:
                if snapshot.health_score_change > 0:
                    trending.append({
                        "niche_id": snapshot.niche_id,
                        "health_score": snapshot.health_score,
                        "health_score_change": snapshot.health_score_change,
                        "lifecycle_stage": snapshot.lifecycle_stage.value,
                        "trend_momentum": snapshot.trend_momentum,
                        "snapshot_date": snapshot.snapshot_date.isoformat()
                    })

            return trending

    async def get_dying_niches(self, limit: int = 10) -> List[Dict]:
        """
        Get niches with declining health scores.

        Args:
            limit: Number of niches to return

        Returns:
            List of declining niches with decline metrics
        """
        async with self.async_session() as session:
            # Get niches with recent negative health score changes
            seven_days_ago = datetime.utcnow() - timedelta(days=7)

            stmt = select(NicheSnapshot).where(
                and_(
                    NicheSnapshot.snapshot_date >= seven_days_ago,
                    NicheSnapshot.health_score_change < 0
                )
            ).order_by(
                NicheSnapshot.health_score_change
            ).limit(limit)

            result = await session.execute(stmt)
            snapshots = result.scalars().all()

            dying = []
            for snapshot in snapshots:
                dying.append({
                    "niche_id": snapshot.niche_id,
                    "health_score": snapshot.health_score,
                    "health_score_change": snapshot.health_score_change,
                    "lifecycle_stage": snapshot.lifecycle_stage.value,
                    "saturation_level": snapshot.saturation_level,
                    "snapshot_date": snapshot.snapshot_date.isoformat()
                })

            return dying

    async def get_emerging_niches(self, limit: int = 10) -> List[Dict]:
        """
        Get new niches in EMERGING stage.

        Args:
            limit: Number of niches to return

        Returns:
            List of emerging niches with opportunity metrics
        """
        async with self.async_session() as session:
            stmt = select(Niche).where(
                and_(
                    Niche.is_active == True,
                    Niche.current_lifecycle_stage == LifecycleStage.EMERGING
                )
            ).order_by(
                desc(Niche.current_health_score)
            ).limit(limit)

            result = await session.execute(stmt)
            niches = result.scalars().all()

            return [
                {
                    "niche_id": n.niche_id,
                    "name": n.name,
                    "description": n.description,
                    "health_score": n.current_health_score,
                    "lifecycle_stage": n.current_lifecycle_stage.value,
                    "entry_timing": n.current_entry_timing.value if n.current_entry_timing else None,
                    "tracked_since": n.tracked_since.isoformat() if n.tracked_since else None
                }
                for n in niches
            ]

    async def compare_niches(self, niche_ids: List[str]) -> Dict:
        """
        Side-by-side comparison of multiple niches.

        Args:
            niche_ids: List of niche IDs to compare

        Returns:
            Comparison matrix with all metrics
        """
        comparisons = []

        for niche_id in niche_ids:
            try:
                analysis = await self.analyze_niche(niche_id, store_snapshot=False)
                comparisons.append(analysis)
            except Exception as e:
                logger.warning(f"Could not analyze {niche_id}: {e}")

        # Find best niche
        if comparisons:
            best_niche = max(comparisons, key=lambda x: x["health_score"])
            best_entry_timing = max(comparisons, key=lambda x: x["entry_timing"]["score"])

            return {
                "niches": comparisons,
                "comparison_count": len(comparisons),
                "best_overall": {
                    "niche_id": best_niche["niche_id"],
                    "health_score": best_niche["health_score"]
                },
                "best_entry_timing": {
                    "niche_id": best_entry_timing["niche_id"],
                    "entry_score": best_entry_timing["entry_timing"]["score"]
                },
                "compared_at": datetime.utcnow().isoformat()
            }

        return {"niches": [], "comparison_count": 0}

    async def get_niche_history(self, niche_id: str, days: int = 90) -> List[Dict]:
        """
        Get historical health scores and metrics for a niche.

        Args:
            niche_id: Niche identifier
            days: Number of days to look back

        Returns:
            List of historical snapshots
        """
        async with self.async_session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            stmt = select(NicheSnapshot).where(
                and_(
                    NicheSnapshot.niche_id == niche_id,
                    NicheSnapshot.snapshot_date >= cutoff_date
                )
            ).order_by(NicheSnapshot.snapshot_date)

            result = await session.execute(stmt)
            snapshots = result.scalars().all()

            return [
                {
                    "snapshot_date": s.snapshot_date.isoformat(),
                    "health_score": s.health_score,
                    "lifecycle_stage": s.lifecycle_stage.value,
                    "saturation_score": s.saturation_score,
                    "trend_momentum": s.trend_momentum,
                    "average_margin": s.average_margin,
                    "entry_timing": s.entry_timing.value
                }
                for s in snapshots
            ]

    async def predict_niche_trajectory(self, niche_id: str) -> Dict:
        """
        Predict where this niche will be in 30/60/90 days.

        Args:
            niche_id: Niche identifier

        Returns:
            Trajectory predictions with confidence levels
        """
        # Get historical data
        history = await self.get_niche_history(niche_id, days=90)

        if len(history) < 7:
            return {
                "niche_id": niche_id,
                "error": "Insufficient historical data (need at least 7 days)",
                "predictions": None
            }

        # Calculate trend from recent history
        recent_scores = [h["health_score"] for h in history[-30:]]
        avg_change_per_day = (recent_scores[-1] - recent_scores[0]) / len(recent_scores)

        current_score = recent_scores[-1]
        current_stage = history[-1]["lifecycle_stage"]

        # Simple linear projection
        predictions = {
            "30_days": {
                "predicted_health_score": round(current_score + (avg_change_per_day * 30), 2),
                "confidence": "medium"
            },
            "60_days": {
                "predicted_health_score": round(current_score + (avg_change_per_day * 60), 2),
                "confidence": "low"
            },
            "90_days": {
                "predicted_health_score": round(current_score + (avg_change_per_day * 90), 2),
                "confidence": "low"
            }
        }

        # Predict stage changes
        for period in predictions:
            predicted_score = predictions[period]["predicted_health_score"]
            predicted_stage = self._score_to_lifecycle_stage(predicted_score)
            predictions[period]["predicted_lifecycle_stage"] = predicted_stage.value
            predictions[period]["stage_will_change"] = (predicted_stage.value != current_stage)

        return {
            "niche_id": niche_id,
            "current_health_score": current_score,
            "current_lifecycle_stage": current_stage,
            "avg_change_per_day": round(avg_change_per_day, 3),
            "trend_direction": "up" if avg_change_per_day > 0 else "down",
            "predictions": predictions,
            "based_on_days": len(history),
            "predicted_at": datetime.utcnow().isoformat()
        }

    async def get_subcategories(self, niche_id: str) -> List[Dict]:
        """
        Break down niche into subcategories with individual scores.

        Args:
            niche_id: Parent niche identifier

        Returns:
            List of subcategories with health scores
        """
        async with self.async_session() as session:
            stmt = select(Niche).where(
                Niche.parent_niche_id == niche_id
            ).order_by(desc(Niche.current_health_score))

            result = await session.execute(stmt)
            subcategories = result.scalars().all()

            return [
                {
                    "niche_id": sub.niche_id,
                    "name": sub.name,
                    "description": sub.description,
                    "health_score": sub.current_health_score,
                    "lifecycle_stage": sub.current_lifecycle_stage.value if sub.current_lifecycle_stage else None,
                    "entry_timing": sub.current_entry_timing.value if sub.current_entry_timing else None,
                    "parent_niche_id": sub.parent_niche_id
                }
                for sub in subcategories
            ]

    # ===== PRIVATE HELPER METHODS =====

    async def _get_or_create_niche(self, session: AsyncSession, niche_id: str) -> Niche:
        """Get existing niche or create new one."""
        stmt = select(Niche).where(Niche.niche_id == niche_id)
        result = await session.execute(stmt)
        niche = result.scalar_one_or_none()

        if not niche:
            niche = Niche(
                niche_id=niche_id,
                name=niche_id.replace("_", " ").title(),
                is_active=True,
                tracked_since=datetime.utcnow()
            )
            session.add(niche)
            await session.commit()
            await session.refresh(niche)
            logger.info(f"Created new niche: {niche_id}")

        return niche

    async def _calculate_trend_momentum(self, session: AsyncSession, niche_id: str) -> Dict:
        """Calculate trend momentum score (0-100) based on product trends in niche."""
        # Get product saturation records for this niche
        sat_stmt = select(ProductSaturation).where(
            ProductSaturation.niche == niche_id
        )
        sat_result = await session.execute(sat_stmt)
        saturation_records = sat_result.scalars().all()

        if not saturation_records:
            return {
                "score": 50.0,  # Neutral if no data
                "search_volume": 0,
                "change_30d": 0.0,
                "change_90d": 0.0,
                "direction": "unknown"
            }

        # Get all ProductIntelligence records (no niche field, use saturation data)
        intel_stmt = select(ProductIntelligence).limit(1000)
        intel_result = await session.execute(intel_stmt)
        intelligence_records = intel_result.scalars().all()

        if not intelligence_records:
            return {
                "score": 50.0,  # Neutral if no data
                "search_volume": 0,
                "change_30d": 0.0,
                "change_90d": 0.0,
                "direction": "unknown"
            }

        # Calculate aggregate metrics
        trend_scores = [i.trend_score for i in intelligence_records if i.trend_score]
        search_volumes = [i.search_volume for i in intelligence_records if i.search_volume]

        if trend_scores:
            avg_trend_score = statistics.mean(trend_scores)
            total_search_volume = sum(search_volumes) if search_volumes else 0

            # Simulate 30d and 90d changes (in production, use historical data)
            change_30d = avg_trend_score - 50  # Simplified
            change_90d = avg_trend_score - 45  # Simplified

            direction = "up" if change_30d > 0 else "down" if change_30d < 0 else "stable"

            return {
                "score": avg_trend_score,
                "search_volume": total_search_volume,
                "change_30d": change_30d,
                "change_90d": change_90d,
                "direction": direction
            }

        return {
            "score": 50.0,
            "search_volume": 0,
            "change_30d": 0.0,
            "change_90d": 0.0,
            "direction": "stable"
        }

    async def _calculate_saturation(self, session: AsyncSession, niche_id: str) -> Dict:
        """Calculate competition/saturation metrics."""
        # Get saturation data for products in this niche
        stmt = select(ProductSaturation).where(
            ProductSaturation.niche == niche_id
        )
        result = await session.execute(stmt)
        saturation_records = result.scalars().all()

        if not saturation_records:
            return {
                "saturation_score": 10.0,  # Low saturation if no data
                "saturation_level": "LOW",
                "seller_count": 0,
                "new_sellers_30d": 0,
                "inverse_score": 90.0  # High inverse score
            }

        # Calculate metrics
        total_users = sum(s.total_users_count for s in saturation_records)
        seller_count = len(saturation_records)

        # Count new sellers (simplified - in production use actual dates)
        new_sellers_30d = sum(1 for s in saturation_records if s.total_users_count < 10)

        # Calculate saturation score (0-100, higher = more saturated)
        avg_saturation = min(100, (total_users / max(1, seller_count)) * 2)

        # Determine saturation level
        saturation_level = "LOW"
        for level, (min_sat, max_sat) in self.SATURATION_LEVELS.items():
            if min_sat <= avg_saturation <= max_sat:
                saturation_level = level
                break

        # Inverse score (100 - saturation = opportunity)
        inverse_score = 100 - avg_saturation

        return {
            "saturation_score": avg_saturation,
            "saturation_level": saturation_level,
            "seller_count": seller_count,
            "new_sellers_30d": new_sellers_30d,
            "inverse_score": inverse_score
        }

    async def _calculate_profit_potential(self, session: AsyncSession, niche_id: str) -> Dict:
        """Calculate profit potential score based on margins."""
        # Get product names in this niche via ProductSaturation
        sat_stmt = select(ProductSaturation).where(
            ProductSaturation.niche == niche_id
        )
        sat_result = await session.execute(sat_stmt)
        saturation_records = sat_result.scalars().all()

        if not saturation_records:
            return {
                "score": 50.0,
                "avg_margin": 0.0,
                "margin_trend": "unknown",
                "price_pressure": "UNKNOWN"
            }

        # Get product names for matching
        product_names = [s.product_name for s in saturation_records]

        # Get products in niche with profit data (match by product name)
        stmt = select(Product).where(Product.product_name.in_(product_names))
        result = await session.execute(stmt)
        products = result.scalars().all()

        if not products:
            return {
                "score": 50.0,
                "avg_margin": 0.0,
                "margin_trend": "unknown",
                "price_pressure": "UNKNOWN"
            }

        # Calculate average margins
        margins = [p.profit_margin for p in products if p.profit_margin]

        if margins:
            avg_margin = statistics.mean(margins)

            # Score based on margin (assume 30%+ is excellent)
            if avg_margin >= 30:
                score = 90.0
            elif avg_margin >= 20:
                score = 70.0
            elif avg_margin >= 10:
                score = 50.0
            else:
                score = 30.0

            # Determine margin trend (simplified)
            margin_trend = "stable"
            price_pressure = "MEDIUM"

            if avg_margin >= 30:
                price_pressure = "LOW"
            elif avg_margin < 10:
                price_pressure = "HIGH"

            return {
                "score": score,
                "avg_margin": avg_margin,
                "margin_trend": margin_trend,
                "price_pressure": price_pressure
            }

        return {
            "score": 50.0,
            "avg_margin": 0.0,
            "margin_trend": "unknown",
            "price_pressure": "UNKNOWN"
        }

    async def _calculate_longevity(self, session: AsyncSession, niche_id: str) -> Dict:
        """Calculate longevity score based on trend stability."""
        # Get historical data for niche
        stmt = select(NicheSnapshot).where(
            NicheSnapshot.niche_id == niche_id
        ).order_by(desc(NicheSnapshot.snapshot_date)).limit(30)

        result = await session.execute(stmt)
        snapshots = result.scalars().all()

        if len(snapshots) < 7:
            # Insufficient data - return moderate score
            return {
                "score": 60.0,
                "is_seasonal": False,
                "stability": 0.7,
                "predicted_lifespan": "12+ months"
            }

        # Calculate stability from variance in health scores
        health_scores = [s.health_score for s in snapshots]

        if len(health_scores) > 1:
            variance = statistics.variance(health_scores)
            # Lower variance = higher stability
            stability = max(0, 1 - (variance / 1000))
        else:
            stability = 0.7

        # Score based on stability
        score = stability * 100

        # Check for seasonality (simplified)
        is_seasonal = False

        # Predict lifespan based on stability and current health
        if stability > 0.8 and health_scores[0] > 60:
            predicted_lifespan = "18+ months"
        elif stability > 0.6 and health_scores[0] > 40:
            predicted_lifespan = "12-18 months"
        elif stability > 0.4:
            predicted_lifespan = "6-12 months"
        else:
            predicted_lifespan = "3-6 months"

        return {
            "score": score,
            "is_seasonal": is_seasonal,
            "stability": stability,
            "predicted_lifespan": predicted_lifespan
        }

    def _determine_lifecycle_stage(
        self,
        health_score: float,
        trend_momentum: float,
        saturation_score: float
    ) -> LifecycleStage:
        """Determine lifecycle stage based on metrics."""
        # EMERGING: High health, low saturation, growing trend
        if health_score >= 70 and saturation_score < 30 and trend_momentum > 60:
            return LifecycleStage.EMERGING

        # GROWTH: Good health, moderate saturation, positive trend
        if health_score >= 50 and saturation_score < 50 and trend_momentum > 50:
            return LifecycleStage.GROWTH

        # PEAK: Fair health, high saturation
        if health_score >= 30 and saturation_score >= 50:
            return LifecycleStage.PEAK

        # DECLINE: Poor health or decreasing trend
        if health_score < 30 or trend_momentum < 30:
            return LifecycleStage.DECLINE

        # DEAD: Very low health
        if health_score < 10:
            return LifecycleStage.DEAD

        # Default to GROWTH
        return LifecycleStage.GROWTH

    def _score_to_lifecycle_stage(self, health_score: float) -> LifecycleStage:
        """Convert health score to lifecycle stage."""
        for stage_name, (min_score, max_score) in self.LIFECYCLE_THRESHOLDS.items():
            if min_score <= health_score <= max_score:
                return LifecycleStage[stage_name]
        return LifecycleStage.GROWTH

    def _evaluate_entry_timing(
        self,
        health_score: float,
        lifecycle_stage: LifecycleStage,
        saturation_score: float,
        avg_margin: float
    ) -> Dict:
        """Evaluate entry timing and risk."""
        # Calculate entry timing score
        # Factors: health (40%), low saturation (30%), profit margin (30%)
        inverse_saturation = 100 - saturation_score
        margin_score = min(100, avg_margin * 3)  # 30% margin = 90 score

        entry_score = (
            (health_score * 0.4) +
            (inverse_saturation * 0.3) +
            (margin_score * 0.3)
        )

        # Determine entry timing
        timing = EntryTiming.FAIR
        for timing_level, (min_s, max_s) in self.ENTRY_TIMING_RANGES.items():
            if min_s <= entry_score <= max_s:
                timing = timing_level
                break

        # Determine risk level
        if saturation_score > 75:
            risk_level = RiskLevel.CRITICAL
        elif saturation_score > 50:
            risk_level = RiskLevel.HIGH
        elif saturation_score > 25:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        # Should enter?
        should_enter = (timing in [EntryTiming.EXCELLENT, EntryTiming.GOOD])

        # ROI estimate
        if avg_margin >= 30:
            roi_estimate = {"min": 25, "max": 50}
        elif avg_margin >= 20:
            roi_estimate = {"min": 15, "max": 35}
        elif avg_margin >= 10:
            roi_estimate = {"min": 5, "max": 20}
        else:
            roi_estimate = {"min": -5, "max": 10}

        # Reasoning
        reasoning = self._generate_entry_reasoning(
            timing,
            lifecycle_stage,
            saturation_score,
            avg_margin
        )

        return {
            "score": entry_score,
            "timing": timing,
            "should_enter": should_enter,
            "risk_level": risk_level,
            "roi_estimate": roi_estimate,
            "reasoning": reasoning
        }

    def _generate_entry_reasoning(
        self,
        timing: EntryTiming,
        lifecycle_stage: LifecycleStage,
        saturation: float,
        margin: float
    ) -> str:
        """Generate human-readable entry timing reasoning."""
        reasons = []

        # Lifecycle assessment
        if lifecycle_stage == LifecycleStage.EMERGING:
            reasons.append("Niche is in EMERGING stage with low competition")
        elif lifecycle_stage == LifecycleStage.GROWTH:
            reasons.append("Niche is in GROWTH stage with accelerating demand")
        elif lifecycle_stage == LifecycleStage.PEAK:
            reasons.append("Niche is at PEAK with maximum competition")
        elif lifecycle_stage == LifecycleStage.DECLINE:
            reasons.append("Niche is DECLINING with decreasing demand")
        elif lifecycle_stage == LifecycleStage.DEAD:
            reasons.append("Niche is DEAD - avoid entry")

        # Saturation assessment
        if saturation < 25:
            reasons.append("Low market saturation presents opportunity")
        elif saturation < 50:
            reasons.append("Moderate competition level")
        elif saturation < 75:
            reasons.append("High saturation may limit success")
        else:
            reasons.append("Critical saturation - market is oversaturated")

        # Margin assessment
        if margin >= 30:
            reasons.append(f"Excellent profit margins ({margin:.1f}%)")
        elif margin >= 20:
            reasons.append(f"Good profit margins ({margin:.1f}%)")
        elif margin >= 10:
            reasons.append(f"Acceptable profit margins ({margin:.1f}%)")
        else:
            reasons.append(f"Low profit margins ({margin:.1f}%) limit profitability")

        return ". ".join(reasons) + "."

    async def _analyze_competitors(self, session: AsyncSession, niche_id: str) -> Dict:
        """Analyze competitor landscape in niche."""
        # Get product saturation records for this niche
        sat_stmt = select(ProductSaturation).where(
            ProductSaturation.niche == niche_id
        ).order_by(desc(ProductSaturation.total_users_count)).limit(10)

        sat_result = await session.execute(sat_stmt)
        saturation_records = sat_result.scalars().all()

        if not saturation_records:
            return {
                "top_competitors": [],
                "barrier_to_entry": "UNKNOWN",
                "avg_reviews": 0
            }

        # Get product names for matching
        product_names = [s.product_name for s in saturation_records]

        # Get corresponding products (match by name)
        stmt = select(Product).where(Product.product_name.in_(product_names)).limit(10)
        result = await session.execute(stmt)
        top_products = result.scalars().all()

        if not top_products:
            return {
                "top_competitors": [],
                "barrier_to_entry": "UNKNOWN",
                "avg_reviews": 0
            }

        # Extract competitor info
        competitors = []
        total_reviews = 0

        for product in top_products:
            # In production, extract brand/seller from product data
            competitors.append({
                "product_name": product.product_name,
                "product_id": product.id
            })
            # Add review count if available
            # total_reviews += product.review_count

        # Determine barrier to entry
        barrier = "MEDIUM"
        if len(competitors) > 7:
            barrier = "HIGH"
        elif len(competitors) < 3:
            barrier = "LOW"

        return {
            "top_competitors": competitors[:5],
            "barrier_to_entry": barrier,
            "avg_reviews": total_reviews // max(1, len(top_products))
        }

    async def _get_top_products(self, session: AsyncSession, niche_id: str, limit: int = 5) -> List[Dict]:
        """Get top products in niche by ranking."""
        # Get product saturation records for this niche
        sat_stmt = select(ProductSaturation).where(
            ProductSaturation.niche == niche_id
        ).order_by(desc(ProductSaturation.total_users_count)).limit(limit)

        sat_result = await session.execute(sat_stmt)
        saturation_records = sat_result.scalars().all()

        if not saturation_records:
            return []

        # Get product names
        product_names = [s.product_name for s in saturation_records]

        # Get products matching these names
        stmt = select(Product).where(Product.product_name.in_(product_names)).limit(limit)
        result = await session.execute(stmt)
        products = result.scalars().all()

        # Build response with saturation data
        return [
            {
                "product_id": p.id,
                "product_name": p.product_name,
                "total_users": next((s.total_users_count for s in saturation_records if s.product_name == p.product_name), 0),
                "saturation_level": "MEDIUM"
            }
            for p in products
        ]

    async def _get_previous_snapshot(self, session: AsyncSession, niche_id: str) -> Optional[NicheSnapshot]:
        """Get most recent previous snapshot."""
        stmt = select(NicheSnapshot).where(
            NicheSnapshot.niche_id == niche_id
        ).order_by(desc(NicheSnapshot.snapshot_date)).limit(1)

        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _store_snapshot(self, session: AsyncSession, niche: Niche, analysis: Dict):
        """Store analysis snapshot in database."""
        snapshot = NicheSnapshot(
            niche_id=niche.niche_id,

            # Core scores
            health_score=analysis["health_score"],
            lifecycle_stage=LifecycleStage(analysis["lifecycle_stage"]),

            # Trend metrics
            search_volume=analysis["trend_momentum"].get("search_volume", 0),
            search_volume_change_30d=analysis["trend_momentum"].get("change_30d", 0),
            search_volume_change_90d=analysis["trend_momentum"].get("change_90d", 0),
            trend_momentum=analysis["trend_momentum"]["score"],

            # Competition metrics
            seller_count=analysis["saturation"]["seller_count"],
            new_sellers_30d=analysis["saturation"].get("new_sellers_30d", 0),
            saturation_score=analysis["saturation"]["score"],
            saturation_level=analysis["saturation"]["level"],

            # Profitability metrics
            average_margin=analysis["profitability"]["avg_margin"],
            margin_trend=analysis["profitability"]["margin_trend"],
            price_pressure=analysis["profitability"]["price_pressure"],

            # Longevity metrics
            is_seasonal=analysis["longevity"]["is_seasonal"],
            trend_stability=analysis["longevity"]["stability"],
            predicted_lifespan=analysis["longevity"]["predicted_lifespan"],
            longevity_score=analysis["longevity"]["score"],

            # Entry recommendation
            entry_timing_score=analysis["entry_timing"]["score"],
            entry_timing=EntryTiming(analysis["entry_timing"]["timing"]),
            should_enter=analysis["entry_timing"]["should_enter"],
            risk_level=RiskLevel(analysis["entry_timing"]["risk_level"]),
            estimated_roi_min=analysis["entry_timing"]["roi_estimate"]["min"],
            estimated_roi_max=analysis["entry_timing"]["roi_estimate"]["max"],
            entry_reasoning=analysis["entry_timing"]["reasoning"],

            # Competitor analysis
            top_competitors=analysis["competitors"]["top_competitors"],
            barrier_to_entry=analysis["competitors"]["barrier_to_entry"],
            average_reviews=analysis["competitors"]["avg_reviews"],

            # Changes
            health_score_change=analysis["changes"]["health_score_change"],
            stage_changed=analysis["changes"]["stage_changed"],

            # Top products
            top_products=analysis["top_products"],

            # Recommendations
            recommendations=analysis["recommendations"],

            # Full analysis
            full_analysis=analysis,

            snapshot_date=datetime.utcnow()
        )

        session.add(snapshot)
        await session.commit()

        logger.info(f"Stored snapshot for niche {niche.niche_id}")

    def _generate_recommendations(
        self,
        niche_id: str,
        health_score: float,
        lifecycle_stage: LifecycleStage,
        saturation_data: Dict,
        profit_data: Dict,
        trend_data: Dict
    ) -> List[str]:
        """Generate strategic recommendations."""
        recommendations = []

        # Entry recommendations
        if lifecycle_stage == LifecycleStage.EMERGING:
            recommendations.append("ENTER NOW: Niche is emerging with low competition")
            recommendations.append("Focus on establishing brand presence early")
        elif lifecycle_stage == LifecycleStage.GROWTH:
            recommendations.append("GOOD TIMING: Enter while growth is accelerating")
            recommendations.append("Differentiate your offering from growing competition")
        elif lifecycle_stage == LifecycleStage.PEAK:
            recommendations.append("CAUTION: Market is at peak saturation")
            recommendations.append("Only enter with strong unique value proposition")
        elif lifecycle_stage == LifecycleStage.DECLINE:
            recommendations.append("AVOID: Niche is declining")
            recommendations.append("Look for emerging subcategories instead")
        elif lifecycle_stage == LifecycleStage.DEAD:
            recommendations.append("DO NOT ENTER: Niche is dead")
            recommendations.append("Find alternative niches immediately")

        # Saturation-based
        if saturation_data["saturation_score"] > 75:
            recommendations.append(f"Critical saturation ({saturation_data['seller_count']} sellers)")
        elif saturation_data["saturation_score"] < 25:
            recommendations.append(f"Low competition ({saturation_data['seller_count']} sellers)")

        # Profit-based
        if profit_data["avg_margin"] >= 30:
            recommendations.append(f"Excellent margins ({profit_data['avg_margin']:.1f}%)")
        elif profit_data["avg_margin"] < 10:
            recommendations.append(f"Low margins ({profit_data['avg_margin']:.1f}%) - consider premium positioning")

        # Trend-based
        if trend_data["direction"] == "up":
            recommendations.append("Positive momentum - demand is growing")
        elif trend_data["direction"] == "down":
            recommendations.append("Negative momentum - demand is declining")

        return recommendations


logger.info("NicheAnalyzer module loaded")
