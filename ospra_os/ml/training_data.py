"""
Training Data Collector - GROK RECOMMENDATION #15

Collects successful operations from the database to create training datasets
for fine-tuning Llama models.

Data Sources:
- Product scoring: High-converting products with actual performance metrics
- Email responses: Successful customer interactions with positive ratings
- Ad copy: High-performing ads with ROAS data
- Pricing decisions: Optimal prices that led to conversions
- Product descriptions: Descriptions that resulted in high click-through rates

Quality Scoring:
- 0-1 score based on actual outcomes (conversions, ratings, ROAS)
- Only collect examples with quality_score >= 0.7
- Higher quality = more weight in fine-tuning

Output Format: JSONL
{"messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
]}
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

logger = logging.getLogger(__name__)


@dataclass
class TrainingExample:
    """Single training example for fine-tuning"""

    task_type: str  # product_scoring, email_response, ad_copy, etc.
    system_prompt: str
    user_prompt: str
    assistant_response: str
    quality_score: float  # 0-1 based on actual outcomes
    metadata: Dict[str, Any]  # Source data, metrics, timestamps

    def to_chat_format(self) -> Dict[str, Any]:
        """Convert to OpenAI chat format for fine-tuning"""
        return {
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": self.user_prompt},
                {"role": "assistant", "content": self.assistant_response}
            ]
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class TrainingDataCollector:
    """
    Collects high-quality training data from operational database.

    Mines successful operations to create training datasets for
    fine-tuning Llama models on OspraOS-specific tasks.

    Target: 1000+ examples per task type for effective fine-tuning.
    """

    def __init__(self, db: Session, output_dir: str = "training_data"):
        self.db = db
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        logger.info(f"TrainingDataCollector initialized, output: {self.output_dir}")

    # ========================================================================
    # PRODUCT SCORING
    # ========================================================================

    def collect_product_scoring_examples(
        self,
        min_quality: float = 0.7,
        limit: int = 1000,
        days_back: int = 90
    ) -> List[TrainingExample]:
        """
        Collect product scoring examples.

        Finds products with:
        - High conversion rates (quality indicator)
        - Significant order volume (statistical validity)
        - Complete metadata (category, price, competition)

        Quality score based on conversion rate and revenue.
        """

        examples = []

        try:
            # Import here to avoid circular dependencies
            from ospra_os.database.multi_store_models import ProductHistory, StoreProduct

            # Query high-performing products
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)

            products = self.db.query(StoreProduct).filter(
                and_(
                    StoreProduct.created_at >= cutoff_date,
                    StoreProduct.conversion_rate >= 0.02,  # At least 2% conversion
                    StoreProduct.total_orders >= 10  # Statistical significance
                )
            ).order_by(desc(StoreProduct.conversion_rate)).limit(limit).all()

            for product in products:
                # Calculate quality score
                # High conversion rate + revenue = high quality
                quality_score = min(1.0, (
                    product.conversion_rate * 20 +  # Normalize 5% CR to 1.0
                    min(product.total_revenue / 1000, 1.0) * 0.5  # Revenue bonus
                ))

                if quality_score < min_quality:
                    continue

                # Build training example
                system_prompt = "You are an e-commerce product analyst. Score products on their potential for success (1-100) based on market data."

                user_prompt = f"""Score this product's e-commerce potential (1-100):

Product: {product.product_name}
Category: {product.category or 'General'}
Price: ${product.price}
Competition: {product.competition_level or 'Medium'}

Provide:
1. Score (1-100)
2. Reasoning (2-3 sentences)
3. Top 3 recommendations

Format as JSON.
"""

                # Assistant response based on actual performance
                score = int(min(100, quality_score * 100))
                assistant_response = json.dumps({
                    "score": score,
                    "reasoning": f"This product shows strong market fit with a {product.conversion_rate*100:.1f}% conversion rate and ${product.total_revenue:.0f} in revenue. The {product.category or 'category'} niche is performing well.",
                    "recommendations": [
                        "Continue current pricing strategy" if product.conversion_rate > 0.03 else "Test 10-15% price reduction",
                        "Expand to related product variations",
                        "Increase marketing spend to scale proven winner"
                    ]
                }, indent=2)

                examples.append(TrainingExample(
                    task_type="product_scoring",
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    assistant_response=assistant_response,
                    quality_score=quality_score,
                    metadata={
                        "product_id": product.id,
                        "product_name": product.product_name,
                        "conversion_rate": float(product.conversion_rate),
                        "revenue": float(product.total_revenue),
                        "orders": product.total_orders,
                        "collected_at": datetime.utcnow().isoformat()
                    }
                ))

            logger.info(f"Collected {len(examples)} product scoring examples")
            return examples

        except Exception as e:
            logger.error(f"Error collecting product scoring examples: {e}")
            return []

    # ========================================================================
    # EMAIL RESPONSES
    # ========================================================================

    def collect_email_response_examples(
        self,
        min_quality: float = 0.7,
        limit: int = 1000,
        days_back: int = 90
    ) -> List[TrainingExample]:
        """
        Collect email response examples.

        Finds email exchanges with:
        - Positive customer ratings
        - Successful resolution (order completed, issue resolved)
        - Professional tone

        Quality score based on customer rating and resolution status.
        """

        # Note: This is a placeholder - actual implementation depends on
        # your email tracking schema. Adjust based on your models.

        examples = []

        logger.info("Email response collection: Schema dependent, skipping for now")
        logger.info("Implement based on your email tracking models")

        return examples

    # ========================================================================
    # AD COPY
    # ========================================================================

    def collect_ad_copy_examples(
        self,
        min_quality: float = 0.7,
        limit: int = 1000,
        days_back: int = 90
    ) -> List[TrainingExample]:
        """
        Collect ad copy examples.

        Finds ads with:
        - High ROAS (return on ad spend)
        - High CTR (click-through rate)
        - Successful conversions

        Quality score based on ROAS and CTR.
        """

        # Note: Placeholder - implement based on your ad tracking schema

        examples = []

        logger.info("Ad copy collection: Schema dependent, skipping for now")
        logger.info("Implement based on your ad tracking models")

        return examples

    # ========================================================================
    # PRODUCT DESCRIPTIONS
    # ========================================================================

    def collect_product_description_examples(
        self,
        min_quality: float = 0.7,
        limit: int = 1000,
        days_back: int = 90
    ) -> List[TrainingExample]:
        """
        Collect product description examples.

        Finds descriptions that led to:
        - High click-through rates
        - High conversion rates
        - Positive reviews mentioning clarity

        Quality score based on CTR and conversion rate.
        """

        examples = []

        try:
            from ospra_os.database.multi_store_models import StoreProduct

            cutoff_date = datetime.utcnow() - timedelta(days=days_back)

            # Get products with descriptions and good performance
            products = self.db.query(StoreProduct).filter(
                and_(
                    StoreProduct.created_at >= cutoff_date,
                    StoreProduct.description.isnot(None),
                    StoreProduct.description != '',
                    StoreProduct.conversion_rate >= 0.02,
                    StoreProduct.total_views >= 100  # Enough traffic to be meaningful
                )
            ).order_by(desc(StoreProduct.conversion_rate)).limit(limit).all()

            for product in products:
                # Calculate quality score
                ctr = product.total_clicks / max(product.total_views, 1)
                quality_score = min(1.0, (
                    product.conversion_rate * 20 +
                    ctr * 5 +
                    (1 if product.average_rating >= 4.5 else 0) * 0.2
                ))

                if quality_score < min_quality:
                    continue

                # Extract features from description (simplified)
                # In production, parse actual features from structured data
                features = ["High quality materials", "Ergonomic design", "Durable construction"]
                benefits = ["Improves comfort", "Long-lasting value", "Professional results"]

                system_prompt = "You are an e-commerce copywriter specializing in product descriptions that convert."

                user_prompt = f"""Write a product description for:

Product: {product.product_name}
Features: {', '.join(features)}
Benefits: {', '.join(benefits)}
Style: Modern, engaging

Write 2-3 compelling paragraphs.
"""

                assistant_response = product.description[:500]  # Use actual high-performing description

                examples.append(TrainingExample(
                    task_type="product_description",
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    assistant_response=assistant_response,
                    quality_score=quality_score,
                    metadata={
                        "product_id": product.id,
                        "product_name": product.product_name,
                        "conversion_rate": float(product.conversion_rate),
                        "ctr": float(ctr),
                        "views": product.total_views,
                        "collected_at": datetime.utcnow().isoformat()
                    }
                ))

            logger.info(f"Collected {len(examples)} product description examples")
            return examples

        except Exception as e:
            logger.error(f"Error collecting product description examples: {e}")
            return []

    # ========================================================================
    # PRICING RECOMMENDATIONS
    # ========================================================================

    def collect_pricing_examples(
        self,
        min_quality: float = 0.7,
        limit: int = 500,
        days_back: int = 90
    ) -> List[TrainingExample]:
        """
        Collect pricing recommendation examples.

        Finds optimal prices that led to:
        - Maximum revenue (price * conversion_rate)
        - Competitive positioning
        - Profit margin optimization

        Quality score based on revenue efficiency.
        """

        examples = []

        try:
            from ospra_os.database.multi_store_models import StoreProduct, ProductHistory

            cutoff_date = datetime.utcnow() - timedelta(days=days_back)

            # Get products with price history and good performance
            products = self.db.query(StoreProduct).filter(
                and_(
                    StoreProduct.created_at >= cutoff_date,
                    StoreProduct.total_orders >= 20,  # Enough data
                    StoreProduct.price > 0
                )
            ).order_by(desc(StoreProduct.total_revenue)).limit(limit).all()

            for product in products:
                # Quality score based on revenue per view (efficiency)
                revenue_per_view = product.total_revenue / max(product.total_views, 1)
                quality_score = min(1.0, revenue_per_view * 100)  # Normalize

                if quality_score < min_quality:
                    continue

                system_prompt = "You are a pricing strategist for e-commerce. Recommend optimal prices based on market data and competition."

                user_prompt = f"""Recommend pricing for:

Product: {product.product_name}
Current Price: ${product.price}
Category: {product.category or 'General'}
Competition: {product.competition_level or 'Medium'}
Current Conversion Rate: {product.conversion_rate*100:.1f}%

What price maximizes revenue?
"""

                # Recommendation based on actual successful price
                assistant_response = f"""Based on market data:

Recommended Price: ${product.price}

Reasoning:
- Current price point shows strong conversion rate ({product.conversion_rate*100:.1f}%)
- Generated ${product.total_revenue:.0f} in revenue with {product.total_orders} orders
- Price-to-value ratio is optimal for this category
- Competition analysis suggests this is the sweet spot

Recommendation: Maintain current pricing. Monitor conversion rate and adjust if it drops below {(product.conversion_rate*0.8)*100:.1f}%.
"""

                examples.append(TrainingExample(
                    task_type="price_recommendation",
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    assistant_response=assistant_response,
                    quality_score=quality_score,
                    metadata={
                        "product_id": product.id,
                        "price": float(product.price),
                        "revenue": float(product.total_revenue),
                        "orders": product.total_orders,
                        "conversion_rate": float(product.conversion_rate),
                        "collected_at": datetime.utcnow().isoformat()
                    }
                ))

            logger.info(f"Collected {len(examples)} pricing examples")
            return examples

        except Exception as e:
            logger.error(f"Error collecting pricing examples: {e}")
            return []

    # ========================================================================
    # COLLECTION ORCHESTRATION
    # ========================================================================

    def collect_all(
        self,
        min_quality: float = 0.7,
        examples_per_task: int = 1000
    ) -> Dict[str, List[TrainingExample]]:
        """
        Collect training data for all task types.

        Returns dict mapping task_type -> list of examples.
        """

        logger.info(f"Collecting training data (min_quality={min_quality})")

        all_examples = {}

        # Collect each task type
        tasks = [
            ("product_scoring", self.collect_product_scoring_examples),
            ("product_description", self.collect_product_description_examples),
            ("price_recommendation", self.collect_pricing_examples),
            ("email_response", self.collect_email_response_examples),
            ("ad_copy", self.collect_ad_copy_examples),
        ]

        for task_type, collector_func in tasks:
            logger.info(f"Collecting {task_type} examples...")
            examples = collector_func(
                min_quality=min_quality,
                limit=examples_per_task
            )
            all_examples[task_type] = examples
            logger.info(f"  ✓ {len(examples)} examples collected")

        # Summary
        total = sum(len(ex) for ex in all_examples.values())
        logger.info(f"Total training examples collected: {total}")

        return all_examples

    def export_to_jsonl(
        self,
        examples: List[TrainingExample],
        task_type: str,
        filename: Optional[str] = None
    ) -> Path:
        """
        Export training examples to JSONL format for fine-tuning.

        Args:
            examples: List of training examples
            task_type: Task type (for filename)
            filename: Custom filename (optional)

        Returns:
            Path to exported file
        """

        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"{task_type}_{timestamp}.jsonl"

        output_path = self.output_dir / filename

        with open(output_path, 'w') as f:
            for example in examples:
                # Write in chat format (one JSON object per line)
                f.write(json.dumps(example.to_chat_format()) + '\n')

        logger.info(f"Exported {len(examples)} examples to {output_path}")
        return output_path

    def export_all(
        self,
        all_examples: Dict[str, List[TrainingExample]]
    ) -> Dict[str, Path]:
        """
        Export all training data to JSONL files.

        Returns dict mapping task_type -> file path.
        """

        exported_files = {}

        for task_type, examples in all_examples.items():
            if examples:  # Only export if we have examples
                file_path = self.export_to_jsonl(examples, task_type)
                exported_files[task_type] = file_path

        logger.info(f"Exported {len(exported_files)} training data files")
        return exported_files

    def get_statistics(
        self,
        all_examples: Dict[str, List[TrainingExample]]
    ) -> Dict[str, Any]:
        """
        Get statistics about collected training data.

        Returns summary with counts, quality scores, etc.
        """

        stats = {
            "total_examples": sum(len(ex) for ex in all_examples.values()),
            "by_task": {},
            "quality": {
                "min": 1.0,
                "max": 0.0,
                "avg": 0.0
            }
        }

        all_scores = []

        for task_type, examples in all_examples.items():
            if examples:
                scores = [ex.quality_score for ex in examples]
                stats["by_task"][task_type] = {
                    "count": len(examples),
                    "avg_quality": sum(scores) / len(scores),
                    "min_quality": min(scores),
                    "max_quality": max(scores)
                }
                all_scores.extend(scores)

        if all_scores:
            stats["quality"]["min"] = min(all_scores)
            stats["quality"]["max"] = max(all_scores)
            stats["quality"]["avg"] = sum(all_scores) / len(all_scores)

        return stats
