"""
COMPETITIVE LEARNING ENGINE

Learns from:
1. Your own product successes and failures
2. Competitor product successes and failures
3. Market patterns across all players

Continuously improves recommendations based on what works vs. what doesn't.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc
import json

from ospra_os.ai.providers.claude import ClaudeProvider
from ospra_os.ai.markdown_stripper import strip_markdown
from ospra_os.database.multi_store_models import Product, ProductStatus, Store


class LearningPattern:
    """Represents a learned pattern from success or failure."""

    def __init__(
        self,
        pattern_type: str,  # "success" or "failure"
        source: str,  # "own_product" or "competitor"
        confidence: float,
        attributes: Dict[str, Any],
        outcome_metrics: Dict[str, float],
        timestamp: datetime
    ):
        self.pattern_type = pattern_type
        self.source = source
        self.confidence = confidence
        self.attributes = attributes
        self.outcome_metrics = outcome_metrics
        self.timestamp = timestamp


class CompetitiveLearningEngine:
    """
    Learns from product performance patterns to improve future recommendations.

    Features:
    - Analyzes what makes YOUR products succeed vs. fail
    - Tracks competitor products and extracts success patterns
    - Identifies market-wide patterns (e.g., "price <$30 converts better in fitness niche")
    - Continuously improves product selection criteria
    - Warns against patterns that have failed before
    """

    def __init__(self, db: Session, claude: ClaudeProvider):
        self.db = db
        self.claude = claude
        self.model = "claude-sonnet-4-5-20250929"

        # In-memory cache of learned patterns
        self.success_patterns = []
        self.failure_patterns = []
        self.competitor_patterns = []

        # Learning thresholds
        self.min_confidence = 0.65
        self.min_sample_size = 3  # Need at least 3 examples to form pattern

    async def learn_from_own_products(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Analyze all your products to extract success and failure patterns.

        Returns patterns like:
        - "Products with 70%+ margin in fitness niche had 85% success rate"
        - "Products priced >$50 in smart_home failed 60% of the time"
        """
        # Get all products with performance data
        query = self.db.query(Product)
        if user_id:
            query = query.join(Store).filter(Store.user_id == user_id)

        products = query.filter(Product.total_sales.isnot(None)).all()

        if len(products) < self.min_sample_size:
            return {
                "patterns_found": 0,
                "reason": f"Need at least {self.min_sample_size} products with sales data",
                "success_patterns": [],
                "failure_patterns": []
            }

        # Classify products as success or failure
        successes = []
        failures = []

        for product in products:
            # Define success criteria
            is_success = (
                product.total_sales > 50 and
                product.profit_margin > 40 and
                product.status == ProductStatus.ACTIVE
            )

            product_data = {
                "id": product.id,
                "title": product.title,
                "price": float(product.price),
                "margin": float(product.profit_margin),
                "sales": product.total_sales,
                "niche": product.store.niche if product.store else "unknown",
                "discovery_score": float(product.discovery_score) if product.discovery_score else 0,
                "velocity_score": float(product.velocity_score) if product.velocity_score else 0,
                "trend_score": float(product.trend_score) if product.trend_score else 0
            }

            if is_success:
                successes.append(product_data)
            else:
                failures.append(product_data)

        # Use AI to extract patterns
        success_patterns = await self._extract_patterns(successes, "success", "own_product")
        failure_patterns = await self._extract_patterns(failures, "failure", "own_product")

        # Store patterns in memory
        self.success_patterns.extend(success_patterns)
        self.failure_patterns.extend(failure_patterns)

        return {
            "patterns_found": len(success_patterns) + len(failure_patterns),
            "success_patterns": [self._pattern_to_dict(p) for p in success_patterns],
            "failure_patterns": [self._pattern_to_dict(p) for p in failure_patterns],
            "products_analyzed": {
                "total": len(products),
                "successes": len(successes),
                "failures": len(failures)
            }
        }

    async def learn_from_competitor(
        self,
        competitor_name: str,
        competitor_products: List[Dict[str, Any]],
        performance_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Learn from competitor product performance.

        Args:
            competitor_name: Name of competitor
            competitor_products: List of their products with attributes
            performance_data: Sales rank, reviews, ratings, etc.

        Returns extracted patterns to replicate their success
        """
        # Classify competitor products by performance
        top_performers = []
        underperformers = []

        for product in competitor_products:
            # Use sales rank, reviews, ratings to classify
            performance_score = self._calculate_competitor_performance_score(
                product,
                performance_data
            )

            product["performance_score"] = performance_score
            product["competitor"] = competitor_name

            if performance_score > 0.7:
                top_performers.append(product)
            elif performance_score < 0.3:
                underperformers.append(product)

        # Extract patterns from their successes
        competitor_success_patterns = await self._extract_patterns(
            top_performers,
            "success",
            f"competitor_{competitor_name}"
        )

        # Learn from their failures (avoid similar products)
        competitor_failure_patterns = await self._extract_patterns(
            underperformers,
            "failure",
            f"competitor_{competitor_name}"
        )

        # Store competitor patterns
        self.competitor_patterns.extend(competitor_success_patterns)
        self.failure_patterns.extend(competitor_failure_patterns)

        return {
            "competitor": competitor_name,
            "patterns_extracted": len(competitor_success_patterns) + len(competitor_failure_patterns),
            "success_patterns": [self._pattern_to_dict(p) for p in competitor_success_patterns],
            "failure_patterns": [self._pattern_to_dict(p) for p in competitor_failure_patterns],
            "products_analyzed": len(competitor_products)
        }

    async def _extract_patterns(
        self,
        products: List[Dict[str, Any]],
        pattern_type: str,
        source: str
    ) -> List[LearningPattern]:
        """
        Use AI to extract common patterns from product data.

        AI analyzes attributes like price, margin, niche, scores
        and identifies what they have in common.
        """
        if len(products) < self.min_sample_size:
            return []

        # Build prompt for AI pattern extraction
        prompt = f"""Analyze these {pattern_type} products and identify patterns.

Products data:
{json.dumps(products, indent=2)}

Find patterns in:
1. Price ranges (e.g., "$20-$40 performs well")
2. Profit margins (e.g., "70%+ margin correlates with success")
3. Niches (e.g., "fitness products with score >8 succeed")
4. Timing (e.g., "seasonal products in Q4")
5. Product attributes (features, categories)

Return ONLY patterns that appear in at least 60% of the products.

Format each pattern as:
PATTERN: [description]
CONFIDENCE: [0.0-1.0]
ATTRIBUTES: [key attributes]
SAMPLE_SIZE: [number]

Return 3-5 strongest patterns only."""

        system_prompt = """You are a data analyst extracting patterns from e-commerce product performance.

FORMATTING REQUIREMENTS:
- NO markdown symbols (no ##, ***, ---, etc.)
- Use plain text only
- Use numbers for lists (1, 2, 3)
- Be specific and quantitative"""

        response = self.claude.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}]
        )

        analysis = strip_markdown(response.content[0].text)

        # Parse AI response into LearningPattern objects
        patterns = self._parse_ai_patterns(analysis, pattern_type, source, products)

        return patterns

    def _parse_ai_patterns(
        self,
        ai_response: str,
        pattern_type: str,
        source: str,
        products: List[Dict[str, Any]]
    ) -> List[LearningPattern]:
        """Parse AI response into structured LearningPattern objects."""
        patterns = []

        # Split response into individual patterns
        lines = ai_response.split('\n')

        current_pattern = {}
        for line in lines:
            line = line.strip()

            if line.startswith('PATTERN:'):
                if current_pattern:
                    # Create LearningPattern from previous pattern
                    patterns.append(self._create_learning_pattern(
                        current_pattern, pattern_type, source, products
                    ))
                current_pattern = {'description': line.replace('PATTERN:', '').strip()}

            elif line.startswith('CONFIDENCE:'):
                try:
                    current_pattern['confidence'] = float(line.replace('CONFIDENCE:', '').strip())
                except:
                    current_pattern['confidence'] = 0.7

            elif line.startswith('ATTRIBUTES:'):
                current_pattern['attributes'] = line.replace('ATTRIBUTES:', '').strip()

            elif line.startswith('SAMPLE_SIZE:'):
                try:
                    current_pattern['sample_size'] = int(line.replace('SAMPLE_SIZE:', '').strip())
                except:
                    current_pattern['sample_size'] = len(products)

        # Add last pattern
        if current_pattern:
            patterns.append(self._create_learning_pattern(
                current_pattern, pattern_type, source, products
            ))

        # Filter by confidence threshold
        patterns = [p for p in patterns if p.confidence >= self.min_confidence]

        return patterns

    def _create_learning_pattern(
        self,
        pattern_dict: Dict[str, Any],
        pattern_type: str,
        source: str,
        products: List[Dict[str, Any]]
    ) -> LearningPattern:
        """Create LearningPattern object from parsed data."""

        # Calculate outcome metrics from products
        outcome_metrics = {
            "avg_sales": sum(p.get("sales", 0) for p in products) / len(products) if products else 0,
            "avg_margin": sum(p.get("margin", 0) for p in products) / len(products) if products else 0,
            "avg_price": sum(p.get("price", 0) for p in products) / len(products) if products else 0,
            "sample_size": len(products)
        }

        return LearningPattern(
            pattern_type=pattern_type,
            source=source,
            confidence=pattern_dict.get('confidence', 0.7),
            attributes={
                "description": pattern_dict.get('description', ''),
                "attributes_list": pattern_dict.get('attributes', ''),
                "sample_size": pattern_dict.get('sample_size', len(products))
            },
            outcome_metrics=outcome_metrics,
            timestamp=datetime.utcnow()
        )

    def _calculate_competitor_performance_score(
        self,
        product: Dict[str, Any],
        performance_data: Dict[str, Any]
    ) -> float:
        """
        Calculate 0-1 performance score for competitor product.

        Uses: sales rank, review count, rating, bestseller badges
        """
        score = 0.0

        # Sales rank (lower is better)
        if "sales_rank" in product:
            rank = product["sales_rank"]
            if rank < 100:
                score += 0.4
            elif rank < 1000:
                score += 0.3
            elif rank < 10000:
                score += 0.2

        # Reviews (more is better)
        if "review_count" in product:
            reviews = product["review_count"]
            if reviews > 1000:
                score += 0.3
            elif reviews > 100:
                score += 0.2
            elif reviews > 10:
                score += 0.1

        # Rating (higher is better)
        if "rating" in product:
            rating = product["rating"]
            if rating >= 4.5:
                score += 0.3
            elif rating >= 4.0:
                score += 0.2
            elif rating >= 3.5:
                score += 0.1

        return min(score, 1.0)

    async def evaluate_product_against_patterns(
        self,
        product: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Check if a product matches success or failure patterns.

        Returns:
        - Similarity to success patterns (good sign)
        - Similarity to failure patterns (warning)
        - Recommendation (launch, test, avoid)
        """
        # Build prompt with all learned patterns
        success_summary = "\n".join([
            f"- {p.attributes['description']} (confidence: {p.confidence:.0%})"
            for p in self.success_patterns[:10]
        ])

        failure_summary = "\n".join([
            f"- {p.attributes['description']} (confidence: {p.confidence:.0%})"
            for p in self.failure_patterns[:10]
        ])

        prompt = f"""Evaluate this product against learned patterns:

PRODUCT:
{json.dumps(product, indent=2)}

SUCCESS PATTERNS (what has worked before):
{success_summary if success_summary else "None yet"}

FAILURE PATTERNS (what has failed before):
{failure_summary if failure_summary else "None yet"}

Analyze:
1. How similar is this product to SUCCESS patterns? (0-100%)
2. How similar is this product to FAILURE patterns? (0-100%)
3. What is the recommended action: LAUNCH, TEST_SMALL, or AVOID?
4. Why? (2-3 specific reasons)

Format:
SUCCESS_MATCH: [percentage]
FAILURE_MATCH: [percentage]
RECOMMENDATION: [LAUNCH/TEST_SMALL/AVOID]
REASONING: [explanation]"""

        system_prompt = """You are an AI analyst using historical patterns to predict product success.

FORMATTING REQUIREMENTS:
- NO markdown symbols (no ##, ***, ---, etc.)
- Use plain text only
- Be specific and quantitative"""

        response = self.claude.client.messages.create(
            model=self.model,
            max_tokens=1500,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}]
        )

        evaluation = strip_markdown(response.content[0].text)

        # Parse evaluation
        result = self._parse_evaluation(evaluation)

        return {
            "product": product.get("title", "Unknown"),
            "success_match": result.get("success_match", 0),
            "failure_match": result.get("failure_match", 0),
            "recommendation": result.get("recommendation", "TEST_SMALL"),
            "reasoning": result.get("reasoning", ""),
            "confidence": result.get("confidence", 0.5),
            "patterns_used": {
                "success_patterns": len(self.success_patterns),
                "failure_patterns": len(self.failure_patterns),
                "competitor_patterns": len(self.competitor_patterns)
            }
        }

    def _parse_evaluation(self, evaluation: str) -> Dict[str, Any]:
        """Parse AI evaluation response."""
        result = {}

        lines = evaluation.split('\n')
        for line in lines:
            line = line.strip()

            if line.startswith('SUCCESS_MATCH:'):
                try:
                    match = line.replace('SUCCESS_MATCH:', '').strip().replace('%', '')
                    result['success_match'] = float(match) / 100
                except:
                    result['success_match'] = 0.5

            elif line.startswith('FAILURE_MATCH:'):
                try:
                    match = line.replace('FAILURE_MATCH:', '').strip().replace('%', '')
                    result['failure_match'] = float(match) / 100
                except:
                    result['failure_match'] = 0.3

            elif line.startswith('RECOMMENDATION:'):
                rec = line.replace('RECOMMENDATION:', '').strip()
                result['recommendation'] = rec

            elif line.startswith('REASONING:'):
                result['reasoning'] = line.replace('REASONING:', '').strip()

        # Calculate confidence based on pattern matches
        if 'success_match' in result and 'failure_match' in result:
            result['confidence'] = result['success_match'] - (result['failure_match'] * 0.5)

        return result

    def _pattern_to_dict(self, pattern: LearningPattern) -> Dict[str, Any]:
        """Convert LearningPattern to dictionary for API responses."""
        return {
            "type": pattern.pattern_type,
            "source": pattern.source,
            "confidence": pattern.confidence,
            "description": pattern.attributes.get("description", ""),
            "outcome_metrics": pattern.outcome_metrics,
            "timestamp": pattern.timestamp.isoformat() if pattern.timestamp else None
        }

    def get_learning_summary(self) -> Dict[str, Any]:
        """Get summary of all learned patterns."""
        return {
            "total_patterns": len(self.success_patterns) + len(self.failure_patterns) + len(self.competitor_patterns),
            "success_patterns": len(self.success_patterns),
            "failure_patterns": len(self.failure_patterns),
            "competitor_patterns": len(self.competitor_patterns),
            "top_success_patterns": [
                self._pattern_to_dict(p)
                for p in sorted(self.success_patterns, key=lambda x: x.confidence, reverse=True)[:5]
            ],
            "top_failure_patterns": [
                self._pattern_to_dict(p)
                for p in sorted(self.failure_patterns, key=lambda x: x.confidence, reverse=True)[:5]
            ],
            "learning_status": "active" if len(self.success_patterns) > 0 else "insufficient_data"
        }


def get_competitive_learning_engine(db: Session) -> CompetitiveLearningEngine:
    """Factory function to create CompetitiveLearningEngine."""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    claude_key = os.getenv("CLAUDE_API_KEY")
    if not claude_key:
        raise ValueError("CLAUDE_API_KEY not found in environment")

    claude = ClaudeProvider(api_key=claude_key)

    return CompetitiveLearningEngine(db, claude)
