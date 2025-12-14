"""
Privacy-Preserving Data Collector - GROK RECOMMENDATION #18

Collects data for federated learning while preserving privacy.

Key Privacy Principles:
1. Only collect from opted-in users
2. Never store raw values — only categories/buckets
3. Apply differential privacy noise where needed
4. Minimum sample sizes before any aggregation
5. No individual user can be identified from outputs
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from ospra_os.database.federated_models import UserContribution, PrivacyConsent

logger = logging.getLogger(__name__)


class PrivacyPreservingCollector:
    """
    Collects data for federated learning while preserving privacy.

    CRITICAL: This class NEVER stores exact values.
    All numeric data is converted to buckets before storage.
    """

    # Minimum users before we aggregate
    MIN_USERS_FOR_AGGREGATION = 10

    # Minimum samples before insight is valid
    MIN_SAMPLES_FOR_INSIGHT = 50

    def __init__(self, db: Session):
        self.db = db

    def is_user_opted_in(self, user_id: int, data_type: str = None) -> bool:
        """Check if user has opted into federated learning"""

        consent = self.db.query(PrivacyConsent).filter(
            PrivacyConsent.user_id == user_id
        ).first()

        if not consent or not consent.federated_learning_enabled:
            return False

        if not consent.contribution_enabled:
            return False

        # Check granular consent
        if data_type == "product" and not consent.contribute_product_data:
            return False
        if data_type == "pricing" and not consent.contribute_pricing_data:
            return False
        if data_type == "ad" and not consent.contribute_ad_data:
            return False

        return True

    def collect_product_outcome(
        self,
        user_id: int,
        niche: str,
        outcome: str,  # success/partial/failure
        price: float = None,
        margin: float = None,
        rating: float = None,
        velocity: int = None
    ) -> Optional[UserContribution]:
        """
        Collect anonymized product deployment outcome.

        We store:
        - Niche category (not product name)
        - Success/failure (not revenue numbers)
        - Price bucket (not exact price)
        - Quality indicators (bucketed)

        We DO NOT store:
        - Product title or identifiers
        - Exact prices or revenue
        - Supplier information
        - Any PII
        """

        if not self.is_user_opted_in(user_id, "product"):
            return None

        # Anonymize and bucket the data
        anonymized_data = {
            "niche": niche,  # Keep category, not product
            "outcome": outcome,  # success/partial/failure
            "price_bucket": self._bucket_price(price) if price else "unknown",
            "margin_bucket": self._bucket_margin(margin) if margin else "unknown",
            "rating_bucket": self._bucket_rating(rating) if rating else "unknown",
            "velocity_bucket": self._bucket_velocity(velocity) if velocity else "unknown",
            "contributed_at": datetime.utcnow().strftime("%Y-%m")  # Month only
        }

        # Create contribution record
        contribution = UserContribution(
            user_id=user_id,
            contribution_type="product_outcome",
            contribution_data=anonymized_data,
            quality_score=1.0
        )

        self.db.add(contribution)
        self.db.commit()

        logger.info(f"Collected anonymized product outcome for user {user_id} in niche {niche}")

        return contribution

    def collect_pricing_outcome(
        self,
        user_id: int,
        niche: str,
        old_price: float,
        new_price: float,
        outcome: str  # improved/maintained/declined
    ) -> Optional[UserContribution]:
        """Collect anonymized pricing decision outcome"""

        if not self.is_user_opted_in(user_id, "pricing"):
            return None

        # Calculate price change direction and magnitude bucket
        change_pct = ((new_price - old_price) / old_price) * 100 if old_price > 0 else 0

        anonymized_data = {
            "niche": niche,
            "price_bucket": self._bucket_price(new_price),
            "change_direction": "increase" if change_pct > 0 else "decrease",
            "change_magnitude": self._bucket_change(abs(change_pct)),
            "outcome": outcome,
            "contributed_at": datetime.utcnow().strftime("%Y-%m")
        }

        contribution = UserContribution(
            user_id=user_id,
            contribution_type="pricing_outcome",
            contribution_data=anonymized_data,
            quality_score=1.0
        )

        self.db.add(contribution)
        self.db.commit()

        return contribution

    def collect_ad_outcome(
        self,
        user_id: int,
        niche: str,
        platform: str,
        roas: float = None,
        ctr: float = None,
        budget: float = None,
        outcome: str = "unknown"
    ) -> Optional[UserContribution]:
        """Collect anonymized ad performance outcome"""

        if not self.is_user_opted_in(user_id, "ad"):
            return None

        anonymized_data = {
            "niche": niche,
            "platform": platform,
            "roas_bucket": self._bucket_roas(roas) if roas else "unknown",
            "ctr_bucket": self._bucket_ctr(ctr) if ctr else "unknown",
            "budget_bucket": self._bucket_budget(budget) if budget else "unknown",
            "outcome": outcome,
            "contributed_at": datetime.utcnow().strftime("%Y-%m")
        }

        contribution = UserContribution(
            user_id=user_id,
            contribution_type="ad_outcome",
            contribution_data=anonymized_data,
            quality_score=1.0
        )

        self.db.add(contribution)
        self.db.commit()

        return contribution

    # ==================== BUCKETING FUNCTIONS ====================
    # These ensure no exact values are ever stored - THIS IS THE PRIVACY GUARANTEE

    def _bucket_price(self, price: float) -> str:
        """Convert exact price to bucket"""
        if price < 10:
            return "under_10"
        elif price < 20:
            return "10_20"
        elif price < 30:
            return "20_30"
        elif price < 50:
            return "30_50"
        elif price < 100:
            return "50_100"
        else:
            return "over_100"

    def _bucket_margin(self, margin: float) -> str:
        """Convert exact margin to bucket"""
        if margin < 20:
            return "under_20"
        elif margin < 30:
            return "20_30"
        elif margin < 40:
            return "30_40"
        elif margin < 50:
            return "40_50"
        else:
            return "over_50"

    def _bucket_rating(self, rating: float) -> str:
        """Convert exact rating to bucket"""
        if rating < 3.5:
            return "under_3.5"
        elif rating < 4.0:
            return "3.5_4.0"
        elif rating < 4.5:
            return "4.0_4.5"
        else:
            return "4.5_plus"

    def _bucket_velocity(self, velocity: int) -> str:
        """Convert velocity score to bucket"""
        if velocity < 30:
            return "low"
        elif velocity < 60:
            return "medium"
        elif velocity < 80:
            return "high"
        else:
            return "very_high"

    def _bucket_change(self, change_pct: float) -> str:
        """Convert price change percentage to bucket"""
        if change_pct < 5:
            return "small"
        elif change_pct < 15:
            return "medium"
        else:
            return "large"

    def _bucket_roas(self, roas: float) -> str:
        """Convert ROAS to bucket"""
        if roas < 1.0:
            return "poor"
        elif roas < 2.0:
            return "average"
        elif roas < 3.0:
            return "good"
        else:
            return "excellent"

    def _bucket_ctr(self, ctr: float) -> str:
        """Convert CTR to bucket"""
        if ctr < 0.5:
            return "low"
        elif ctr < 1.5:
            return "average"
        elif ctr < 3.0:
            return "good"
        else:
            return "excellent"

    def _bucket_budget(self, budget: float) -> str:
        """Convert daily budget to bucket"""
        if budget < 20:
            return "low"
        elif budget < 50:
            return "medium"
        elif budget < 100:
            return "high"
        else:
            return "very_high"
