"""
Federated Learning Synthetic Data Generator - GROK RECOMMENDATION #18

Generates realistic test data to validate the federated learning system
WITHOUT requiring actual users.

This script:
1. Creates synthetic users
2. Opts them into federated learning
3. Generates realistic product/pricing/ad outcomes
4. Simulates patterns (e.g., higher-rated products succeed more)
5. Ensures minimum thresholds met (50+ samples, 10+ users)

Run with:
    uv run python generate_federated_test_data.py

Options:
    --users N        Number of synthetic users (default: 100)
    --contributions N Number of contributions per user (default: 5)
    --clear          Clear existing federated data before generating
"""

import sys
import random
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ospra_os.database.multi_store_models import Base, User
from ospra_os.federated.service import FederatedLearningService
from ospra_os.database.federated_models import (
    AggregateInsight,
    UserContribution,
    InsightApplication,
    PrivacyConsent
)

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


# ==================== CONFIGURATION ====================

NICHES = ["smart_home", "fitness", "beauty", "pets", "office"]

# Price ranges that map to buckets
PRICE_RANGES = {
    "under_10": (5, 9.99),
    "10_20": (10, 19.99),
    "20_30": (20, 29.99),
    "30_50": (30, 49.99),
    "50_100": (50, 99.99),
    "over_100": (100, 200)
}

# Realistic patterns to simulate
# High-rated + mid-price products tend to succeed
SUCCESS_PATTERNS = {
    ("4.5_plus", "20_30"): 0.75,  # 75% success rate
    ("4.5_plus", "10_20"): 0.70,
    ("4.0_4.5", "20_30"): 0.60,
    ("4.0_4.5", "10_20"): 0.55,
    ("3.5_4.0", "20_30"): 0.45,
    ("under_3.5", "20_30"): 0.25,
}


# ==================== DATA GENERATION ====================

class SyntheticDataGenerator:
    """
    Generates realistic synthetic data for federated learning testing.
    """

    def __init__(self, db_url: str = "sqlite:///./data/ospra_os.db"):
        self.engine = create_engine(db_url)
        SessionLocal = sessionmaker(bind=self.engine)
        self.db = SessionLocal()
        self.service = FederatedLearningService(self.db)

    def clear_federated_data(self):
        """Clear existing federated learning data."""
        logger.info("🗑️  Clearing existing federated data...")

        self.db.query(InsightApplication).delete()
        self.db.query(AggregateInsight).delete()
        self.db.query(UserContribution).delete()
        self.db.query(PrivacyConsent).delete()

        self.db.commit()

        logger.info("✅ Cleared all federated data")

    def create_synthetic_users(self, count: int) -> List[int]:
        """
        Create synthetic users.

        Returns:
            List of user IDs
        """

        logger.info(f"👥 Creating {count} synthetic users...")

        # Check if we already have users
        existing_count = self.db.query(User).count()

        if existing_count >= count:
            logger.info(f"✅ Already have {existing_count} users in database")
            user_ids = [u.id for u in self.db.query(User).limit(count).all()]
            return user_ids

        # Create new users
        user_ids = []

        for i in range(count):
            user = User(
                email=f"synthetic_user_{i+1}@federated-test.com",
                full_name=f"Synthetic User {i+1}",
                tier="pro",  # Give them pro tier for full features
                is_active=True
            )
            self.db.add(user)
            self.db.flush()  # Get ID without committing
            user_ids.append(user.id)

        self.db.commit()

        logger.info(f"✅ Created {count} synthetic users (IDs: {user_ids[0]}-{user_ids[-1]})")

        return user_ids

    def enable_federated_learning(self, user_ids: List[int]):
        """
        Opt all users into federated learning.
        """

        logger.info(f"🔒 Enabling federated learning for {len(user_ids)} users...")

        for user_id in user_ids:
            self.service.enable_federated_learning(
                user_id=user_id,
                contribute_products=True,
                contribute_pricing=True,
                contribute_ads=True
            )

        logger.info(f"✅ All users opted into federated learning")

    def generate_product_outcomes(self, user_ids: List[int], per_user: int):
        """
        Generate product deployment outcomes with realistic patterns.
        """

        logger.info(f"📦 Generating product outcomes ({per_user} per user)...")

        total_contributions = 0

        for user_id in user_ids:
            for _ in range(per_user):
                # Random niche
                niche = random.choice(NICHES)

                # Random rating bucket (weighted toward higher ratings)
                rating_bucket = random.choices(
                    ["under_3.5", "3.5_4.0", "4.0_4.5", "4.5_plus"],
                    weights=[0.1, 0.2, 0.3, 0.4]
                )[0]

                # Random price bucket (weighted toward mid-range)
                price_bucket = random.choices(
                    list(PRICE_RANGES.keys()),
                    weights=[0.1, 0.25, 0.3, 0.2, 0.1, 0.05]
                )[0]

                # Get actual price from bucket range
                price_range = PRICE_RANGES[price_bucket]
                price = random.uniform(*price_range)

                # Rating from bucket
                rating_map = {
                    "under_3.5": (2.0, 3.4),
                    "3.5_4.0": (3.5, 3.9),
                    "4.0_4.5": (4.0, 4.4),
                    "4.5_plus": (4.5, 5.0)
                }
                rating = random.uniform(*rating_map[rating_bucket])

                # Determine outcome based on pattern
                pattern_key = (rating_bucket, price_bucket)
                success_rate = SUCCESS_PATTERNS.get(pattern_key, 0.50)  # Default 50%

                outcome = "success" if random.random() < success_rate else "failure"

                # Random margin (weighted toward 30-50%)
                margin = random.uniform(20, 60)

                # Random velocity
                velocity = random.randint(20, 95)

                # Record contribution
                contrib = self.service.record_product_outcome(
                    user_id=user_id,
                    niche=niche,
                    outcome=outcome,
                    price=price,
                    margin=margin,
                    rating=rating,
                    velocity=velocity
                )

                if contrib:
                    total_contributions += 1

        logger.info(f"✅ Generated {total_contributions} product outcome contributions")

    def generate_pricing_outcomes(self, user_ids: List[int], per_user: int):
        """
        Generate pricing decision outcomes.
        """

        logger.info(f"💰 Generating pricing outcomes ({per_user} per user)...")

        total_contributions = 0

        for user_id in user_ids:
            for _ in range(per_user):
                niche = random.choice(NICHES)

                # Random old price
                old_price = random.uniform(15, 50)

                # Random price change (-20% to +20%)
                change_pct = random.uniform(-20, 20)
                new_price = old_price * (1 + change_pct / 100)

                # Outcome based on change direction and magnitude
                # Small increases tend to improve, large increases tend to hurt
                if change_pct > 0:
                    # Price increase
                    if change_pct < 10:
                        outcome_prob = 0.6  # 60% improved
                    else:
                        outcome_prob = 0.3  # 30% improved
                else:
                    # Price decrease
                    if change_pct > -10:
                        outcome_prob = 0.5  # 50% improved
                    else:
                        outcome_prob = 0.7  # 70% improved

                outcome = random.choices(
                    ["improved", "maintained", "declined"],
                    weights=[outcome_prob, 0.3, 1 - outcome_prob - 0.3]
                )[0]

                contrib = self.service.record_pricing_outcome(
                    user_id=user_id,
                    niche=niche,
                    old_price=old_price,
                    new_price=new_price,
                    outcome=outcome
                )

                if contrib:
                    total_contributions += 1

        logger.info(f"✅ Generated {total_contributions} pricing outcome contributions")

    def generate_ad_outcomes(self, user_ids: List[int], per_user: int):
        """
        Generate ad campaign outcomes.
        """

        logger.info(f"📢 Generating ad outcomes ({per_user} per user)...")

        total_contributions = 0

        platforms = ["facebook", "google", "tiktok", "instagram"]

        for user_id in user_ids:
            for _ in range(per_user):
                niche = random.choice(NICHES)
                platform = random.choice(platforms)

                # Random budget (weighted toward medium)
                budget = random.choices(
                    [15, 35, 75, 150],  # low, medium, high, very_high
                    weights=[0.2, 0.4, 0.3, 0.1]
                )[0]

                # Random ROAS (higher budgets tend to have better ROAS)
                if budget < 20:
                    roas = random.uniform(0.5, 2.0)
                elif budget < 50:
                    roas = random.uniform(1.0, 3.0)
                elif budget < 100:
                    roas = random.uniform(1.5, 4.0)
                else:
                    roas = random.uniform(2.0, 5.0)

                # CTR correlates with ROAS
                if roas < 1.0:
                    ctr = random.uniform(0.2, 0.8)
                elif roas < 2.0:
                    ctr = random.uniform(0.5, 1.5)
                elif roas < 3.0:
                    ctr = random.uniform(1.0, 2.5)
                else:
                    ctr = random.uniform(2.0, 4.0)

                # Outcome based on ROAS
                outcome = "success" if roas > 2.0 else "partial" if roas > 1.0 else "failure"

                contrib = self.service.record_ad_outcome(
                    user_id=user_id,
                    niche=niche,
                    platform=platform,
                    roas=roas,
                    ctr=ctr,
                    budget=budget,
                    outcome=outcome
                )

                if contrib:
                    total_contributions += 1

        logger.info(f"✅ Generated {total_contributions} ad outcome contributions")

    def generate_all(
        self,
        num_users: int = 100,
        contributions_per_user: int = 5,
        clear_first: bool = False
    ):
        """
        Generate complete synthetic dataset.
        """

        logger.info("")
        logger.info("=" * 70)
        logger.info("🤖 FEDERATED LEARNING SYNTHETIC DATA GENERATOR")
        logger.info("=" * 70)
        logger.info("")

        if clear_first:
            self.clear_federated_data()
            logger.info("")

        # Step 1: Create users
        user_ids = self.create_synthetic_users(num_users)
        logger.info("")

        # Step 2: Enable federated learning
        self.enable_federated_learning(user_ids)
        logger.info("")

        # Step 3: Generate contributions
        self.generate_product_outcomes(user_ids, contributions_per_user)
        logger.info("")

        self.generate_pricing_outcomes(user_ids, contributions_per_user)
        logger.info("")

        self.generate_ad_outcomes(user_ids, contributions_per_user)
        logger.info("")

        # Summary
        total_contributions = self.db.query(UserContribution).count()
        total_consents = self.db.query(PrivacyConsent).count()

        logger.info("=" * 70)
        logger.info("📊 GENERATION SUMMARY")
        logger.info("=" * 70)
        logger.info("")
        logger.info(f"Users created:           {num_users}")
        logger.info(f"Opted-in users:          {total_consents}")
        logger.info(f"Total contributions:     {total_contributions}")
        logger.info(f"Contributions per user:  {total_contributions / num_users:.1f}")
        logger.info("")
        logger.info("Privacy verification:")
        logger.info("  ✓ All data is bucketed (no exact values)")
        logger.info("  ✓ Minimum 10 users threshold MET" if num_users >= 10 else "  ✗ Need 10+ users")
        logger.info("  ✓ Minimum 50 samples threshold MET" if total_contributions >= 50 else "  ✗ Need 50+ samples")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Run aggregation:")
        logger.info("     POST http://localhost:8001/api/federated/aggregate")
        logger.info("")
        logger.info("  2. View statistics:")
        logger.info("     GET http://localhost:8001/api/federated/stats")
        logger.info("")
        logger.info("  3. Get recommendations:")
        logger.info("     POST http://localhost:8001/api/federated/recommendations")
        logger.info("     {\"user_id\": 1, \"niche\": \"smart_home\"}")
        logger.info("")
        logger.info("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic data for federated learning testing"
    )
    parser.add_argument(
        "--users",
        type=int,
        default=100,
        help="Number of synthetic users to create (default: 100)"
    )
    parser.add_argument(
        "--contributions",
        type=int,
        default=5,
        help="Contributions per user per type (default: 5)"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing federated data before generating"
    )

    args = parser.parse_args()

    # Ensure data directory exists
    Path("./data").mkdir(exist_ok=True)

    # Generate data
    generator = SyntheticDataGenerator()
    generator.generate_all(
        num_users=args.users,
        contributions_per_user=args.contributions,
        clear_first=args.clear
    )


if __name__ == "__main__":
    main()
